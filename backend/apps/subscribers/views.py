import csv
import io
import logging
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.db.models import Count, Q
from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView
from apps.accounts.authentication import ApiKeyAuthentication
from rest_framework.response import Response
from .models import SubscriberList, Subscriber
from .serializers import SubscriberSerializer, SubscriberListSerializer
from apps.accounts.serializers import get_admin_user

logger = logging.getLogger(__name__)


def _get_or_create_default_list(user):
    from apps.accounts.serializers import get_admin_user
    shared = get_admin_user() or user
    lst = SubscriberList.objects.filter(user=shared).order_by("created_at").first()
    if lst:
        return lst
    return SubscriberList.objects.create(user=shared, name="Mi newsletter")


def _resolve_list(list_id, shared):
    """Devuelve el grupo (SubscriberList) `list_id` si pertenece a `shared`;
    si no se indica o no existe, cae al grupo por defecto."""
    if list_id:
        lst = SubscriberList.objects.filter(pk=list_id, user=shared).first()
        if lst:
            return lst
    return _get_or_create_default_list(shared)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def groups(request):
    """Lista (GET) o crea (POST) grupos de suscriptores del usuario."""
    shared = get_admin_user() or request.user
    if request.method == "POST":
        name = (request.data.get("name") or "").strip()
        if not name:
            return Response({"detail": "El nombre del grupo es obligatorio."}, status=400)
        lst = SubscriberList.objects.create(
            user=shared,
            name=name[:200],
            description=(request.data.get("description") or "")[:2000],
        )
        return Response(SubscriberListSerializer(lst).data, status=201)
    qs = SubscriberList.objects.filter(user=shared).order_by("created_at")
    return Response(SubscriberListSerializer(qs, many=True).data)


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def group_detail(request, pk):
    """Renombra (PATCH) o elimina (DELETE) un grupo. Al eliminar se borran sus
    suscriptores (cascade). Siempre debe quedar al menos un grupo."""
    shared = get_admin_user() or request.user
    try:
        lst = SubscriberList.objects.get(pk=pk, user=shared)
    except SubscriberList.DoesNotExist:
        return Response({"detail": "Grupo no encontrado."}, status=404)

    if request.method == "DELETE":
        if SubscriberList.objects.filter(user=shared).count() <= 1:
            return Response(
                {"detail": "No puedes eliminar el único grupo que tienes."}, status=400
            )
        lst.delete()
        return Response(status=204)

    if "name" in request.data:
        name = (request.data.get("name") or "").strip()
        if not name:
            return Response({"detail": "El nombre del grupo no puede estar vacío."}, status=400)
        lst.name = name[:200]
    if "description" in request.data:
        lst.description = (request.data.get("description") or "")[:2000]
    lst.save()
    return Response(SubscriberListSerializer(lst).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def all_subscribers(request):
    shared = get_admin_user() or request.user

    # Ámbito: ?list=<id> filtra por un grupo; sin él, agrega TODOS los grupos.
    list_id = request.query_params.get("list")
    selected = None
    base = Subscriber.objects.filter(list__user=shared)
    if list_id:
        selected = SubscriberList.objects.filter(pk=list_id, user=shared).first()
        if selected:
            base = base.filter(list=selected)

    qs = base.order_by("-subscribed_at")

    # Filtro opcional por email/nombre (server-side).
    search = (request.query_params.get("search") or "").strip()
    if search:
        qs = qs.filter(
            Q(email__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
        )

    # Paginación por query params (?page=N&page_size=M). page_size por defecto 50,
    # máximo 200.
    try:
        page_size = int(request.query_params.get("page_size", 50))
    except (ValueError, TypeError):
        page_size = 50
    page_size = max(1, min(page_size, 200))
    try:
        page_number = int(request.query_params.get("page", 1))
    except (ValueError, TypeError):
        page_number = 1

    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page_number)  # clampa fuera de rango

    # "sendable" = activos que NO están dentro de una automatización (enrolamiento
    # activo). Es a quien realmente le llegará una campaña, ya que el envío excluye
    # a los que están recibiendo una secuencia de automatización.
    # NOTA: se calcula sobre el ámbito completo (no la página) y sin el filtro de
    # búsqueda, porque lo usa el editor de campañas.
    from apps.automations.models import AutomationEnrollment
    in_automation = AutomationEnrollment.objects.filter(
        status="active", automation__user=shared
    ).values("subscriber_id")
    sendable = base.filter(status="active").exclude(id__in=in_automation).count()

    return Response({
        "list_id": selected.id if selected else None,
        # count = TOTAL de resultados (con filtro aplicado si lo hay), no por página.
        "count": paginator.count,
        "sendable_count": sendable,
        "page": page_obj.number,
        "page_size": page_size,
        "num_pages": paginator.num_pages,
        "total_pages": paginator.num_pages,
        "results": SubscriberSerializer(page_obj.object_list, many=True).data,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_all(request):
    shared = get_admin_user() or request.user
    list_id = request.query_params.get("list")
    qs = Subscriber.objects.filter(list__user=shared)
    if list_id:
        selected = SubscriberList.objects.filter(pk=list_id, user=shared).first()
        if selected:
            qs = qs.filter(list=selected)
    return _csv_response(qs, "subscribers.csv")


# Alias de cabeceras reconocidas (en minúsculas). El importador es "listo":
# detecta la columna de email aunque se llame distinto y, si no, la auto-detecta.
_EMAIL_ALIASES = (
    "email", "e-mail", "e_mail", "email address", "emailaddress", "correo",
    "correo electrónico", "correo electronico", "correo_electronico", "mail",
    "suscriptor", "subscriber", "address", "dirección", "direccion", "destinatario",
)
_FIRST_ALIASES = (
    "first_name", "first name", "firstname", "nombre", "name", "fname",
    "given name", "given_name", "nombre completo", "full name", "fullname",
)
_LAST_ALIASES = (
    "last_name", "last name", "lastname", "apellido", "apellidos",
    "surname", "lname", "family name", "family_name",
)
# Cabeceras de "nombre completo" que conviene partir en nombre + apellido.
_FULLNAME_HEADERS = ("nombre", "name", "nombre completo", "full name", "fullname")


def _looks_like_email(v):
    v = (v or "").strip()
    return "@" in v and "." in v.rsplit("@", 1)[-1]


def _parse_subscribers(csv_data):
    """Extrae (email, first_name, last_name) de un CSV o de un TXT (un email por
    línea). Detecta la columna de email por alias de cabecera y, si no, la
    auto-detecta buscando la columna con direcciones de email. Ignora cualquier
    columna que no reconozca. Devuelve también filas inválidas como
    (None, "", "") para poder contarlas como omitidas."""
    first_line = next((ln for ln in csv_data.splitlines() if ln.strip()), "")
    delim = ";" if first_line.count(";") > first_line.count(",") else ","
    is_csv = (delim in first_line) or (first_line.strip().lower() in _EMAIL_ALIASES)

    if not is_csv:
        out = []
        for line in csv_data.splitlines():
            email = line.strip()
            if email and _looks_like_email(email):
                out.append((email.lower(), "", ""))
            elif email:
                out.append((None, "", ""))
        return out

    reader = csv.DictReader(io.StringIO(csv_data), delimiter=delim)
    fieldnames = [f for f in (reader.fieldnames or []) if f is not None]

    def _find(aliases):
        for f in fieldnames:
            if (f or "").strip().lower() in aliases:
                return f
        return None

    email_key = _find(_EMAIL_ALIASES)
    first_key = _find(_FIRST_ALIASES)
    last_key = _find(_LAST_ALIASES)
    rows = list(reader)

    # Auto-detección: si ninguna cabecera coincide, usar la columna cuyas celdas
    # parezcan emails (la que más @ tenga en las primeras filas).
    if email_key is None and fieldnames:
        best, best_n = None, 0
        for f in fieldnames:
            n = sum(1 for r in rows[:100] if _looks_like_email(r.get(f)))
            if n > best_n:
                best, best_n = f, n
        email_key = best if best_n else None

    out = []
    for r in rows:
        email = (r.get(email_key) or "").strip() if email_key else ""
        if not _looks_like_email(email):
            # último recurso: cualquier celda de la fila con pinta de email
            email = next((str(v).strip() for v in r.values() if _looks_like_email(v)), "")
        if not _looks_like_email(email):
            out.append((None, "", ""))
            continue
        first = (r.get(first_key) or "").strip() if first_key else ""
        last = (r.get(last_key) or "").strip() if last_key else ""
        # Si solo hay una columna de "nombre completo", partir en nombre/apellido.
        if first and not last and not last_key and \
                (first_key or "").strip().lower() in _FULLNAME_HEADERS:
            parts = first.split(None, 1)
            if len(parts) == 2:
                first, last = parts[0], parts[1]
        out.append((email.lower(), first[:100], last[:100]))
    return out


def import_subscribers(lst, csv_data):
    """Importa a `lst` desde CSV/TXT. Devuelve (imported, skipped). Usa
    bulk_create para soportar listas grandes (decenas de miles) sin timeouts."""
    existing = set(Subscriber.objects.filter(list=lst).values_list("email", flat=True))
    seen = set()
    to_create = []
    skipped = 0
    for email, first, last in _parse_subscribers(csv_data):
        if not email:
            skipped += 1            # fila sin email válido
            continue
        if email in existing or email in seen:
            skipped += 1            # duplicado (ya en la lista o repetido en el CSV)
            continue
        seen.add(email)
        to_create.append(Subscriber(
            list=lst, email=email[:254], first_name=first, last_name=last,
        ))
    if to_create:
        Subscriber.objects.bulk_create(to_create, batch_size=500, ignore_conflicts=True)
    return len(to_create), skipped


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def import_all(request):
    shared = get_admin_user() or request.user
    lst = _resolve_list(request.data.get("list") or request.query_params.get("list"), shared)
    csv_data = request.data.get("csv_data") or ""
    if not csv_data and request.FILES.get("file"):
        csv_data = request.FILES["file"].read().decode("utf-8-sig", errors="ignore")
    else:
        csv_data = csv_data.lstrip("﻿")  # quita BOM si vino como texto
    if not csv_data:
        return Response({"detail": "csv_data o file requerido"}, status=400)

    imported, skipped = import_subscribers(lst, csv_data)
    return Response({"imported": imported, "skipped": skipped})


@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
def subscriber_detail(request, pk):
    try:
        sub = Subscriber.objects.get(pk=pk, list__user=get_admin_user() or request.user)
    except Subscriber.DoesNotExist:
        return Response({"detail": "no encontrado"}, status=404)
    if request.method == "DELETE":
        sub.delete()
        return Response(status=204)
    for f in ("email", "first_name", "last_name", "status"):
        if f in request.data:
            setattr(sub, f, request.data[f])
    sub.save()
    return Response(SubscriberSerializer(sub).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_subscriber(request):
    shared = get_admin_user() or request.user
    lst = _resolve_list(request.data.get("list"), shared)
    email = (request.data.get("email") or "").strip().lower()
    if not email:
        return Response({"detail": "email requerido"}, status=400)
    sub, created = Subscriber.objects.get_or_create(
        list=lst,
        email=email,
        defaults={
            "first_name": request.data.get("first_name", ""),
            "last_name": request.data.get("last_name", ""),
        },
    )
    return Response(SubscriberSerializer(sub).data, status=201 if created else 200)


class _ApiSubscribeIPThrottle(SimpleRateThrottle):
    """Límite por IP evaluado ANTES de autenticar (en initial()), para que una
    ráfaga de keys inválidas no quede sin límite: DRF comprueba los throttles
    después de la auth, y un AuthenticationFailed se salta esa comprobación.
    No mira request.user (evita forzar la auth perezosa)."""

    scope = "api_subscribe_ip"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class _ApiKeyThrottle(SimpleRateThrottle):
    """Límite por API key (no por usuario). Todas las keys autentican como el
    admin compartido, así que un ScopedRateThrottle las metería en un único cubo;
    esto aísla cada integración usando request.auth (la instancia ApiKey)."""

    scope = "api_subscribe"

    def get_cache_key(self, request, view):
        key = getattr(request, "auth", None)
        if key is None or getattr(key, "pk", None) is None:
            return None   # sin key válida no aplica (ya lo cubre el throttle por IP)
        return self.cache_format % {"scope": self.scope, "ident": str(key.pk)}


class PublicAddSubscriberView(APIView):
    """Alta de suscriptor vía API key externa (Authorization: Bearer <key>).
    Crea directamente en estado activo (sin doble opt-in). Solo POST, sin lectura.
    Autenticación exclusiva por API key (sin fallback de cookie JWT)."""

    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [_ApiKeyThrottle]   # por-key; se evalúa tras autenticar

    def initial(self, request, *args, **kwargs):
        # Límite por IP pre-auth: acota el volumen total (incluidas keys inválidas)
        # antes de que la auth pueda cortocircuitar la cadena de throttling.
        ip_throttle = _ApiSubscribeIPThrottle()
        if not ip_throttle.allow_request(request, self):
            self.throttled(request, ip_throttle.wait())
        super().initial(request, *args, **kwargs)

    def post(self, request):
        shared = get_admin_user() or request.user
        lst = _resolve_list(request.data.get("list"), shared)   # grupo opcional, acotado al owner (evita IDOR)
        email = (request.data.get("email") or "").strip().lower()
        if not email:
            return Response({"detail": "email requerido"}, status=400)
        try:
            validate_email(email)   # rechaza direcciones mal formadas / con saltos de línea
        except ValidationError:
            return Response({"detail": "email inválido"}, status=400)
        sub, created = Subscriber.objects.get_or_create(
            list=lst,
            email=email,
            defaults={
                "first_name": (request.data.get("first_name") or "")[:100],
                "last_name": (request.data.get("last_name") or "")[:100],
            },
        )
        return Response(SubscriberSerializer(sub).data, status=201 if created else 200)


def _csv_safe(value):
    """Neutraliza inyección de fórmulas CSV (CWE-1236). El nombre/apellido de un
    suscriptor es entrada pública (formulario de alta sin auth, import CSV): si
    empieza por =, +, -, @, tab o CR, una hoja de cálculo (Excel/LibreOffice/
    Sheets) lo interpretaría como fórmula al abrir el export. Se antepone un
    apóstrofo para forzar que la celda se trate como texto literal."""
    s = "" if value is None else str(value)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + s
    return s


def _csv_response(subscribers, filename):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["email", "first_name", "last_name", "status", "subscribed_at"])
    for s in subscribers:
        writer.writerow([
            _csv_safe(s.email), _csv_safe(s.first_name), _csv_safe(s.last_name),
            s.status, s.subscribed_at,
        ])
    response = HttpResponse(output.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def low_engagement(request):
    """
    Devuelve suscriptores activos ordenados por tasa de apertura ascendente.
    Solo incluye quienes han recibido al menos 1 campaña.
    Query param: threshold (int, default 25) — devuelve solo los que abren menos de ese %.

    Uses a single annotated queryset instead of per-subscriber queries (avoids N+1).
    """
    try:
        threshold = int(request.query_params.get("threshold", 25))
    except (ValueError, TypeError):
        threshold = 25

    lst = _get_or_create_default_list(request.user)

    # Annotate each active subscriber with:
    #   sends_count — number of distinct campaigns sent to this subscriber
    #   opens_count — number of distinct campaigns this subscriber opened
    # NOTE: count distinct *campaigns*, not raw rows. Each pixel load creates a new
    # EmailOpen row, so Count("emailopen") would tally every open event and let
    # open_rate exceed 100% (a subscriber opening one email 5×). We want the share
    # of campaigns opened, so we count distinct emailopen__campaign.
    qs = (
        Subscriber.objects.filter(list=lst, status="active")
        .annotate(
            sends_count=Count(
                "campaignsend__campaign",
                filter=Q(campaignsend__campaign__user=get_admin_user() or request.user),
                distinct=True,
            ),
            opens_count=Count(
                "emailopen__campaign",
                filter=Q(emailopen__campaign__user=get_admin_user() or request.user),
                distinct=True,
            ),
        )
        .filter(sends_count__gt=0)
    )

    results = []
    for sub in qs:
        open_rate = round(sub.opens_count / sub.sends_count * 100, 1)
        if open_rate < threshold:
            results.append(
                {
                    "id": str(sub.id),
                    "email": sub.email,
                    "first_name": sub.first_name,
                    "last_name": sub.last_name,
                    "sends_count": sub.sends_count,
                    "opens_count": sub.opens_count,
                    "open_rate": open_rate,
                }
            )

    results.sort(key=lambda x: (x["open_rate"], -x["sends_count"]))
    return Response(results[:200])


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def bulk_delete(request):
    """Elimina suscriptores por lista de IDs. Solo puede borrar los suyos."""
    ids = request.data.get("ids", [])
    if not isinstance(ids, list) or len(ids) == 0:
        return Response({"detail": "ids debe ser una lista no vacía"}, status=400)
    if len(ids) > 500:
        return Response({"detail": "Máximo 500 IDs por petición"}, status=400)
    deleted_count, _ = Subscriber.objects.filter(
        pk__in=ids, list__user=get_admin_user() or request.user
    ).delete()
    return Response({"deleted": deleted_count})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def move_subscribers(request):
    """Mueve suscriptores (por lista de IDs) a otro grupo (`target_list`).

    Como `Subscriber` tiene `unique_together(list, email)`, se omiten los emails
    que ya existan en el grupo destino (y los que ya estén en él). Devuelve
    cuántos se movieron y cuántos se omitieron."""
    shared = get_admin_user() or request.user
    ids = request.data.get("ids", [])
    target_id = request.data.get("target_list")
    if not isinstance(ids, list) or len(ids) == 0:
        return Response({"detail": "ids debe ser una lista no vacía"}, status=400)
    if len(ids) > 500:
        return Response({"detail": "Máximo 500 IDs por petición"}, status=400)

    target = SubscriberList.objects.filter(pk=target_id, user=shared).first()
    if not target:
        return Response({"detail": "Grupo destino no válido"}, status=400)

    subs = list(Subscriber.objects.filter(pk__in=ids, list__user=shared))
    # Emails ya presentes en el grupo destino (para no violar unique_together).
    existing = set(
        Subscriber.objects.filter(
            list=target, email__in=[s.email for s in subs]
        ).values_list("email", flat=True)
    )
    to_move, skipped = [], 0
    seen = set(existing)
    for s in subs:
        if s.list_id == target.id or s.email in seen:
            skipped += 1
            continue
        seen.add(s.email)          # evita choques de email duplicado dentro del lote
        to_move.append(s.pk)

    moved = 0
    if to_move:
        moved = Subscriber.objects.filter(pk__in=to_move).update(list=target)
    return Response({"moved": moved, "skipped": skipped, "target": target.name})
