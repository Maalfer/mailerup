import logging
import shutil
import uuid
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.accounts.authentication import CookieJWTAuthentication, ApiKeyAuthentication
from .models import Campaign
from .serializers import CampaignSerializer, CampaignListSerializer
from .tasks import _personalize

logger = logging.getLogger(__name__)


def _ensure_list(campaign, user):
    # Si se envía a todos los grupos no hace falta una lista concreta.
    if campaign.send_to_all:
        return
    if not campaign.subscriber_list:
        from apps.subscribers.views import _get_or_create_default_list
        campaign.subscriber_list = _get_or_create_default_list(user)
        campaign.save(update_fields=["subscriber_list"])


class CampaignViewSet(viewsets.ModelViewSet):
    # Además de la cookie JWT (panel), acepta una API key (Bearer): permite que un
    # sistema externo o un asistente IA (Claude vía MCP/API) cree, programe, pause,
    # reanude o borre campañas con la clave generada en Ajustes → Claves API.
    authentication_classes = [CookieJWTAuthentication, ApiKeyAuthentication]

    def get_queryset(self):
        from apps.accounts.serializers import get_admin_user
        return Campaign.objects.filter(user=get_admin_user() or self.request.user)

    def get_serializer_class(self):
        if self.action == "list":
            return CampaignListSerializer
        return CampaignSerializer

    def perform_create(self, serializer):
        from apps.accounts.serializers import get_admin_user
        serializer.save(user=get_admin_user() or self.request.user)

    @action(detail=True, methods=["post"])
    def send(self, request, pk=None):
        campaign = self.get_object()
        if campaign.status == "paused":
            return Response(
                {"detail": "La campaña está pausada. Usa el botón ▶ Reanudar para continuar el envío."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if campaign.status == "sending":
            return Response(
                {"detail": "La campaña ya se está enviando."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if campaign.status not in ("draft", "scheduled", "failed"):
            return Response({"detail": "La campaña ya fue enviada."}, status=status.HTTP_400_BAD_REQUEST)
        _ensure_list(campaign, request.user)
        # Reintento de una campaña fallida: borra los envíos que dieron error para
        # que esos destinatarios se reintenten (los entregados con éxito se respetan).
        if campaign.status == "failed":
            campaign.sends.filter(provider_message_id__startswith="error:").delete()
        # Envío inmediato y NO bloqueante: marcamos la campaña como "sending" y
        # devolvemos enseguida. El scheduler in-process la va enviando por lotes
        # a un ritmo controlado (envío progresivo), sin bloquear la petición HTTP
        # ni saturar al proveedor con miles de correos de golpe.
        campaign.scheduled_at = None
        campaign.status = "sending"
        campaign.save(update_fields=["scheduled_at", "status"])
        return Response({
            "detail": "Envío iniciado. Los correos se irán entregando de forma progresiva.",
            "status": campaign.status,
        })

    @action(detail=True, methods=["post"])
    def schedule(self, request, pk=None):
        campaign = self.get_object()
        if campaign.status not in ("draft", "scheduled"):
            return Response(
                {"detail": "Solo puedes programar borradores o campañas ya programadas."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        raw = request.data.get("scheduled_at") or ""
        scheduled_at = parse_datetime(raw)
        if not scheduled_at:
            return Response(
                {"detail": "scheduled_at requerido en formato ISO 8601."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if timezone.is_naive(scheduled_at):
            scheduled_at = timezone.make_aware(scheduled_at, timezone.get_current_timezone())
        if scheduled_at <= timezone.now():
            return Response(
                {"detail": "La fecha de envío debe ser futura."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        _ensure_list(campaign, request.user)
        campaign.scheduled_at = scheduled_at
        campaign.status = "scheduled"
        campaign.save(update_fields=["scheduled_at", "status"])
        return Response({
            "detail": "Campaña programada.",
            "status": campaign.status,
            "scheduled_at": campaign.scheduled_at,
        })

    @action(detail=True, methods=["post"])
    def unschedule(self, request, pk=None):
        campaign = self.get_object()
        if campaign.status != "scheduled":
            return Response(
                {"detail": "La campaña no está programada."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        campaign.scheduled_at = None
        campaign.status = "draft"
        campaign.save(update_fields=["scheduled_at", "status"])
        return Response({"detail": "Programación cancelada.", "status": campaign.status})

    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        """Pausa un envío en curso: el scheduler deja de enviar esta campaña."""
        campaign = self.get_object()
        if campaign.status != "sending":
            return Response(
                {"detail": "Solo se puede pausar una campaña que se está enviando."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        campaign.status = "paused"
        campaign.save(update_fields=["status"])
        return Response({"detail": "Envío pausado.", "status": campaign.status})

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        """Reanuda un envío pausado: continúa con los pendientes al ritmo
        configurado, SIN reenviar a quienes ya recibieron el correo."""
        campaign = self.get_object()
        if campaign.status != "paused":
            return Response(
                {"detail": "Solo se puede reanudar una campaña pausada."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        _ensure_list(campaign, request.user)
        campaign.status = "sending"
        campaign.save(update_fields=["status"])
        return Response({
            "detail": "Envío reanudado. Continúa con los pendientes (no reenvía a los ya enviados).",
            "status": campaign.status,
        })

    @action(detail=True, methods=["post"])
    def send_test(self, request, pk=None):
        campaign = self.get_object()
        email = (request.data.get("email") or "").strip()
        if not email:
            return Response({"detail": "email requerido"}, status=status.HTTP_400_BAD_REQUEST)
        if not campaign.from_email:
            return Response(
                {"detail": "La campaña no tiene remitente (from_email) configurado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from apps.subscribers.models import Subscriber
        from apps.integrations.email_sender import get_sender
        # Ghost subscriber: uses a random UUID that does not exist in the DB.
        # _personalize will sign this UUID into tracking/unsubscribe tokens — the
        # tokens are cryptographically valid but will resolve to no real subscriber
        # when the email recipient opens or clicks. This is intentional for test sends.
        ghost = Subscriber(id=uuid.uuid4(), email=email, first_name="Test", last_name="User")
        try:
            sender = get_sender(campaign.user)
            html = _personalize(campaign.html_content, ghost, campaign)
            sender.send(
                to_email=email,
                to_name="Test User",
                from_name=campaign.from_name,
                from_email=campaign.from_email,
                subject=f"[TEST] {campaign.subject}",
                html=html,
                campaign_id=str(campaign.id),
                subscriber_id=str(ghost.id),
            )
        except Exception as exc:
            logger.exception("Error sending test email for campaign %s: %s", campaign.id, exc)
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": f"Email de prueba enviado a {email}"})

    @action(detail=True, methods=["post", "delete"], url_path="exclude")
    def exclusion(self, request, pk=None):
        """POST: añade emails a excluir (CSV/TXT). DELETE: vacía la exclusión.

        Una sola acción para los dos métodos: dos @action con el mismo url_path
        chocan en el router de DRF y dejan uno inalcanzable (POST daba 405)."""
        if request.method == "DELETE":
            campaign = self.get_object()
            campaign.excluded_emails = ""
            campaign.save(update_fields=["excluded_emails"])
            return Response({"detail": "Lista de exclusión eliminada."})

        import csv, io
        campaign = self.get_object()

        csv_data = ""
        if request.FILES.get("file"):
            csv_data = request.FILES["file"].read().decode("utf-8", errors="ignore")
        elif request.data.get("csv_data"):
            csv_data = request.data["csv_data"]

        if not csv_data:
            return Response({"detail": "Fichero o csv_data requerido."}, status=400)

        emails = set()
        lines = csv_data.strip().splitlines()

        first_line = lines[0].lower() if lines else ""
        if "email" in first_line and "," in first_line:
            for row in csv.DictReader(io.StringIO(csv_data)):
                norm = {(k or "").lower().strip(): (v or "").strip() for k, v in row.items()}
                e = norm.get("email", "").lower().strip()
                if e and "@" in e:
                    emails.add(e)
        else:
            for line in lines:
                e = line.strip().lower().split(",")[0].strip()
                if e and "@" in e and "." in e:
                    emails.add(e)

        if not emails:
            return Response({"detail": "No se encontraron emails válidos en el fichero."}, status=400)

        existing = set(filter(None, campaign.excluded_emails.splitlines()))
        merged = existing | emails
        campaign.excluded_emails = "\n".join(sorted(merged))
        campaign.save(update_fields=["excluded_emails"])

        return Response({
            "detail": f"{len(emails)} emails añadidos a la exclusión.",
            "total_excluded": len(merged),
        })

    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        campaign = self.get_object()
        campaign.pk = None
        campaign.name = f"{campaign.name} (copia)"
        campaign.status = "draft"
        campaign.sent_at = None
        campaign.scheduled_at = None
        campaign.save()
        return Response(CampaignSerializer(campaign).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def preview(self, request, pk=None):
        """HTML del correo TAL CUAL lo reciben los suscriptores: personalizado con
        un destinatario de ejemplo, con el pie de baja y los enlaces reescritos
        (mismo `_personalize` que el envío real). Para verlo en un visor/iframe."""
        campaign = self.get_object()
        from apps.subscribers.models import Subscriber
        # Suscriptor "fantasma" con UUID aleatorio (no existe en la BD): los tokens
        # de baja/tracking son válidos pero no resuelven a nadie, igual que send_test.
        ghost = Subscriber(
            id=uuid.uuid4(), email="suscriptor@ejemplo.com",
            first_name="Nombre", last_name="Apellido",
        )
        html = _personalize(campaign.html_content, ghost, campaign)
        return Response({
            "html": html,
            "subject": campaign.subject,
            "from_name": campaign.from_name,
            "from_email": campaign.from_email,
        })


import os
from pathlib import Path
from django.conf import settings
from django.db.models import Sum
from django.http import FileResponse, Http404
from .models import Resource
from .serializers import ResourceSerializer

# Límites de almacenamiento por propietario (evita DoS por agotamiento de disco).
MAX_RESOURCES_PER_USER = 200
MAX_STORAGE_PER_USER = 500 * 1024 * 1024  # 500 MB

# Extensiones que el navegador renderiza/ejecuta inline (vector de XSS). Se
# rechazan en la subida; serve_resource añade defensa en profundidad.
BLOCKED_UPLOAD_EXTS = {
    # Render/ejecución en el navegador (XSS en el mismo origen del panel).
    '.svg', '.html', '.htm', '.xhtml', '.shtml', '.xml', '.xsl',
    '.js', '.mjs', '.mhtml', '.swf', '.htc',
    # Ejecutables del lado servidor: hoy nginx sirve estos ficheros como
    # estáticos (sin intérprete), pero se bloquean por defensa en profundidad
    # para que un futuro cambio de servidor/vhost no derive en RCE.
    '.php', '.php3', '.php4', '.php5', '.php7', '.phtml', '.pht', '.phar',
    '.jsp', '.jspx', '.asp', '.aspx', '.ashx', '.cgi', '.pl', '.py',
    '.rb', '.sh', '.bash', '.exe', '.com', '.bat', '.cmd', '.ps1', '.jar',
}
# Tipos seguros de servir inline; cualquier otro se fuerza como descarga.
INLINE_SAFE_EXTS = {
    '.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.ico', '.pdf',
}


class ResourceViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'delete', 'head', 'options']
    serializer_class = ResourceSerializer

    def get_queryset(self):
        from apps.accounts.serializers import get_admin_user
        return Resource.objects.filter(user=get_admin_user() or self.request.user)

    def create(self, request, *args, **kwargs):
        file = request.FILES.get('file')
        if not file:
            return Response({'detail': 'file requerido.'}, status=status.HTTP_400_BAD_REQUEST)
        if file.size > 25 * 1024 * 1024:
            return Response({'detail': 'El fichero no puede superar 25 MB.'}, status=status.HTTP_400_BAD_REQUEST)

        ext = os.path.splitext(file.name)[1].lower()
        if ext in BLOCKED_UPLOAD_EXTS:
            return Response(
                {'detail': f'Tipo de fichero no permitido ({ext}).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.accounts.serializers import get_admin_user
        owner = get_admin_user() or request.user

        # Quota por propietario: nº de ficheros y almacenamiento total (anti-DoS).
        owned = Resource.objects.filter(user=owner)
        if owned.count() >= MAX_RESOURCES_PER_USER:
            return Response(
                {'detail': f'Límite de recursos alcanzado ({MAX_RESOURCES_PER_USER}).'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        used = owned.aggregate(total=Sum('file_size'))['total'] or 0
        if used + file.size > MAX_STORAGE_PER_USER:
            return Response(
                {'detail': 'Límite de almacenamiento alcanzado (500 MB).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        resource_id = uuid.uuid4()
        stored_name = Resource.make_stored_name(resource_id, file.name)
        dest = Path(settings.MEDIA_ROOT) / 'resources' / stored_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, 'wb') as f:
            for chunk in file.chunks():
                f.write(chunk)

        resource = Resource.objects.create(
            id=resource_id,
            user=owner,
            original_name=file.name,
            stored_name=stored_name,
            content_type=file.content_type or '',
            file_size=file.size,
        )
        return Response(ResourceSerializer(resource).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        resource = self.get_object()
        path = Path(settings.MEDIA_ROOT) / 'resources' / resource.stored_name
        if path.exists():
            path.unlink(missing_ok=True)
        resource.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='disk-usage')
    def disk_usage(self, request):
        usage = shutil.disk_usage('/')
        resources_dir = Path(settings.MEDIA_ROOT) / 'resources'
        resources_bytes = sum(
            f.stat().st_size for f in resources_dir.rglob('*') if f.is_file()
        ) if resources_dir.exists() else 0
        return Response({
            'total': usage.total,
            'used': usage.used,
            'free': usage.free,
            'resources_bytes': resources_bytes,
        })


def serve_resource(request, name):
    if '/' in name or '\\' in name or '..' in name:
        raise Http404
    resources_dir = (Path(settings.MEDIA_ROOT) / 'resources').resolve()
    path = (resources_dir / name).resolve()
    try:
        path.relative_to(resources_dir)
    except ValueError:
        raise Http404
    if not path.exists() or not path.is_file():
        raise Http404
    # Solo se sirven inline tipos seguros (imágenes/pdf). Cualquier otro
    # (.svg, .html, etc.) se fuerza como descarga para evitar que el navegador
    # ejecute su contenido como XSS en el mismo origen que el panel.
    ext = os.path.splitext(name)[1].lower()
    inline = ext in INLINE_SAFE_EXTS
    response = FileResponse(open(path, 'rb'), as_attachment=not inline, filename=name)
    # Evita MIME sniffing (un fichero "inocente" reinterpretado como HTML/SVG).
    response['X-Content-Type-Options'] = 'nosniff'
    return response
