import os
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import FileResponse, Http404
from django.utils.text import slugify
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import ApiKey
from .serializers import (
    UserSerializer, ChangePasswordSerializer, AdminUserSerializer, ApiKeySerializer,
)
from .serializers import get_admin_user

User = get_user_model()


PROVIDER_PRESETS = {
    "local": {
        "label": "Local (no envía)", "host": "", "port": 0, "tls": False, "ssl": False, "kind": "local",
        "dns": None,
    },
    "smtp_generic": {
        "label": "SMTP genérico", "host": "", "port": 587, "tls": True, "ssl": False, "kind": "smtp",
        "dns": {
            "spf_record": "v=spf1 mx ~all",
            "spf_note": "Si tu servidor de correo es el mismo que tu MX (lo más habitual en hostings compartidos), con 'mx ~all' basta. Si tu proveedor te indica un include específico, añádelo.",
            "dkim_note": "Pregunta a tu proveedor de SMTP cómo activar DKIM. Tendrás que publicar un TXT en <selector>._domainkey.{domain} con la clave pública que te den.",
            "dmarc_record": "v=DMARC1; p=none; rua=mailto:dmarc@{domain}",
            "guide_url": "",
        },
    },
    "raiola": {
        "label": "Raiola Networks", "host": "smtp.tudominio.com", "port": 465, "tls": False, "ssl": True, "kind": "smtp",
        "hint": "Usa el host SMTP que te dio Raiola (suele ser smtp.<tudominio>). Puerto 465 SSL o 587 STARTTLS.",
        "dns": {
            "spf_record": "v=spf1 a mx include:raiolanetworks.com ~all",
            "spf_note": "Raiola incluye su propio SPF para los correos salientes desde sus servidores compartidos. Añádelo en un TXT en la raíz del dominio (@).",
            "dkim_note": "Activa DKIM desde el Panel de Cliente de Raiola → 'Correo' → 'Configurar DKIM'. Te dará la clave pública para publicar en TXT en raiola._domainkey.{domain} (el selector suele ser 'raiola' o 'default').",
            "dmarc_record": "v=DMARC1; p=none; rua=mailto:dmarc@{domain}",
            "guide_url": "https://soporte.raiolanetworks.com/configuracion-spf-dkim-y-dmarc/",
        },
    },
    "gmail": {
        "label": "Gmail", "host": "smtp.gmail.com", "port": 587, "tls": True, "ssl": False, "kind": "smtp",
        "hint": "Necesitas una App Password (no tu contraseña normal).",
        "dns": {
            "spf_record": "v=spf1 include:_spf.google.com ~all",
            "spf_note": "Si usas Google Workspace para tu dominio, este es el SPF correcto. Si usas Gmail personal (@gmail.com), no puedes configurar SPF de @gmail.com — usa otro From.",
            "dkim_note": "Activa DKIM en admin.google.com → Apps → Google Workspace → Gmail → Autenticar correo. Te darán un TXT a publicar en google._domainkey.{domain}.",
            "dmarc_record": "v=DMARC1; p=none; rua=mailto:dmarc@{domain}",
            "guide_url": "https://support.google.com/a/answer/33786",
        },
    },
    "outlook": {
        "label": "Outlook / Office 365", "host": "smtp.office365.com", "port": 587, "tls": True, "ssl": False, "kind": "smtp",
        "dns": {
            "spf_record": "v=spf1 include:spf.protection.outlook.com -all",
            "spf_note": "Microsoft requiere SPF para enviar desde tu dominio vía Office 365.",
            "dkim_note": "Activa DKIM desde Microsoft 365 Defender Portal → Email & collaboration → Policies → DKIM. Te genera dos CNAME (selector1._domainkey.{domain} y selector2._domainkey.{domain}).",
            "dmarc_record": "v=DMARC1; p=none; rua=mailto:dmarc@{domain}",
            "guide_url": "https://learn.microsoft.com/microsoft-365/security/office-365-security/email-authentication-dkim-configure",
        },
    },
    "yahoo": {
        "label": "Yahoo Mail", "host": "smtp.mail.yahoo.com", "port": 587, "tls": True, "ssl": False, "kind": "smtp",
        "hint": "Necesitas una App Password en Yahoo.",
        "dns": {
            "spf_record": "v=spf1 include:_spf.mail.yahoo.com ~all",
            "spf_note": "Si usas el SMTP de Yahoo con tu dominio propio (Yahoo Business), añade este SPF.",
            "dkim_note": "Yahoo no permite generar DKIM para dominios externos en cuentas gratuitas. Solo está disponible en planes empresariales.",
            "dmarc_record": "v=DMARC1; p=none; rua=mailto:dmarc@{domain}",
            "guide_url": "",
        },
    },
    "icloud": {
        "label": "iCloud Mail", "host": "smtp.mail.me.com", "port": 587, "tls": True, "ssl": False, "kind": "smtp",
        "hint": "Genera una App Password en appleid.apple.com.",
        "dns": {
            "spf_record": "v=spf1 include:icloud.com ~all",
            "spf_note": "Para enviar desde tu dominio vía iCloud Mail con dominio personalizado (iCloud+).",
            "dkim_note": "Apple gestiona DKIM automáticamente cuando configuras un dominio personalizado en iCloud+. Te indicará los CNAMEs en el panel de iCloud.",
            "dmarc_record": "v=DMARC1; p=none; rua=mailto:dmarc@{domain}",
            "guide_url": "https://support.apple.com/en-us/HT212524",
        },
    },
    "zoho": {
        "label": "Zoho Mail", "host": "smtp.zoho.com", "port": 587, "tls": True, "ssl": False, "kind": "smtp",
        "dns": {
            "spf_record": "v=spf1 include:zohomail.com ~all",
            "spf_note": "Si tu servidor Zoho está en .eu, usa 'include:zohomail.eu' en su lugar.",
            "dkim_note": "Activa DKIM en mailadmin.zoho.com → Email Configuration → DKIM. Te darán un TXT para zoho._domainkey.{domain} (selector configurable).",
            "dmarc_record": "v=DMARC1; p=none; rua=mailto:dmarc@{domain}",
            "guide_url": "https://www.zoho.com/mail/help/adminconsole/dkim-configuration.html",
        },
    },
    "hostinger": {
        "label": "Hostinger", "host": "smtp.hostinger.com", "port": 465, "tls": False, "ssl": True, "kind": "smtp",
        "dns": {
            "spf_record": "v=spf1 include:_spf.mail.hostinger.com ~all",
            "spf_note": "Hostinger publica su SPF en _spf.mail.hostinger.com.",
            "dkim_note": "Activa DKIM en hPanel → Emails → Tu dominio → Configuración DKIM. Hostinger publicará el TXT automáticamente si gestionas el DNS allí, si no te lo dará para que lo publiques en hostingermail._domainkey.{domain}.",
            "dmarc_record": "v=DMARC1; p=none; rua=mailto:dmarc@{domain}",
            "guide_url": "https://support.hostinger.com/en/articles/1583234-how-to-set-up-email-spf-dkim-and-dmarc-records",
        },
    },
    "ionos": {
        "label": "IONOS", "host": "smtp.ionos.es", "port": 587, "tls": True, "ssl": False, "kind": "smtp",
        "dns": {
            "spf_record": "v=spf1 include:_spf-frontend.mail.ionos.es ~all",
            "spf_note": "Para IONOS España. Si tu IONOS es .com o .de, usa el include de esa región (_spf-frontend.mail.ionos.com).",
            "dkim_note": "Activa DKIM desde el panel IONOS → Email → Tu dominio → Seguridad. Si gestionas tu DNS en IONOS lo activa solo, si no te dará un TXT para ionos1._domainkey.{domain}.",
            "dmarc_record": "v=DMARC1; p=none; rua=mailto:dmarc@{domain}",
            "guide_url": "https://www.ionos.es/ayuda/email/correo-electronico-profesional/configurar-spf-y-dkim/",
        },
    },
    "ovh": {
        "label": "OVH", "host": "ssl0.ovh.net", "port": 465, "tls": False, "ssl": True, "kind": "smtp",
        "dns": {
            "spf_record": "v=spf1 include:mx.ovh.com ~all",
            "spf_note": "OVH publica su SPF en mx.ovh.com. Sirve tanto para MX Plan como Email Pro.",
            "dkim_note": "Genera DKIM desde Manager OVH → Web Cloud → Emails → Tu dominio → DKIM. Te darán la clave para publicar en ovh._domainkey.{domain}.",
            "dmarc_record": "v=DMARC1; p=none; rua=mailto:dmarc@{domain}",
            "guide_url": "https://help.ovhcloud.com/csm/es-dns-spf-record",
        },
    },
    "dondominio": {
        "label": "DonDominio", "host": "smtp.dondominio.com", "port": 587, "tls": True, "ssl": False, "kind": "smtp",
        "dns": {
            "spf_record": "v=spf1 include:_spf.dondominio.com ~all",
            "spf_note": "Para correos enviados desde la plataforma de email de DonDominio.",
            "dkim_note": "Activa DKIM desde Panel DonDominio → Mi Email → Tu dominio → DKIM. Lo publica automáticamente si tu DNS está delegado a DonDominio.",
            "dmarc_record": "v=DMARC1; p=none; rua=mailto:dmarc@{domain}",
            "guide_url": "https://www.dondominio.com/ayuda/email/spf-dkim/",
        },
    },
    "ses": {
        "label": "Amazon SES (SMTP)", "host": "email-smtp.eu-west-1.amazonaws.com", "port": 587, "tls": True, "ssl": False, "kind": "smtp",
        "hint": "Cambia la región del host según tu SES (eu-west-1, us-east-1, etc.).",
        "dns": {
            "spf_record": "v=spf1 include:amazonses.com ~all",
            "spf_note": "Necesario para que AWS SES pueda enviar desde tu dominio.",
            "dkim_note": "Activa 'Easy DKIM' en la consola de SES → Verified identities → Tu dominio → DKIM. SES te dará 3 CNAMEs para selector1._domainkey.{domain}, selector2._domainkey.{domain} y selector3._domainkey.{domain}.",
            "dmarc_record": "v=DMARC1; p=none; rua=mailto:dmarc@{domain}",
            "guide_url": "https://docs.aws.amazon.com/ses/latest/dg/send-email-authentication-dkim.html",
        },
    },
    "mailgun": {
        "label": "Mailgun (SMTP)", "host": "smtp.mailgun.org", "port": 587, "tls": True, "ssl": False, "kind": "smtp",
        "dns": {
            "spf_record": "v=spf1 include:mailgun.org ~all",
            "spf_note": "Configura también el MX si vas a recibir webhooks vía Mailgun.",
            "dkim_note": "Mailgun te da el TXT al verificar el dominio. El selector es 'k1' (o el que indiquen): k1._domainkey.{domain}.",
            "dmarc_record": "v=DMARC1; p=none; rua=mailto:dmarc@{domain}",
            "guide_url": "https://documentation.mailgun.com/docs/mailgun/user-manual/sending-messages/#authentication",
        },
    },
    "postmark": {
        "label": "Postmark (SMTP)", "host": "smtp.postmarkapp.com", "port": 587, "tls": True, "ssl": False, "kind": "smtp",
        "hint": "User y password son ambos tu Server Token.",
        "dns": {
            "spf_record": "v=spf1 a mx include:spf.mtasv.net ~all",
            "spf_note": "Postmark exige Sender Signatures verificadas. Sin DKIM válido, el envío será rechazado por ellos mismos.",
            "dkim_note": "En Postmark → Sender Signatures → Verify Domain. Te dan un TXT en <token>._domainkey.{domain} con un selector único por cuenta.",
            "dmarc_record": "v=DMARC1; p=none; rua=mailto:dmarc@{domain}",
            "guide_url": "https://postmarkapp.com/support/article/1098-how-to-set-up-dkim-for-domains-using-postmark",
        },
    },
    "mailjet": {
        "label": "Mailjet (SMTP)", "host": "in-v3.mailjet.com", "port": 587, "tls": True, "ssl": False, "kind": "smtp",
        "dns": {
            "spf_record": "v=spf1 include:spf.mailjet.com ~all",
            "spf_note": "Necesario para que Mailjet pueda enviar desde tu dominio.",
            "dkim_note": "Activa DKIM en Mailjet → Account → Domains → Authenticate. Te darán un TXT para mailjet._domainkey.{domain}.",
            "dmarc_record": "v=DMARC1; p=none; rua=mailto:dmarc@{domain}",
            "guide_url": "https://documentation.mailjet.com/hc/articles/360042412734",
        },
    },
    "sparkpost": {
        "label": "SparkPost (SMTP)", "host": "smtp.sparkpostmail.com", "port": 587, "tls": True, "ssl": False, "kind": "smtp",
        "hint": "User: SMTP_Injection. Password: tu API key.",
        "dns": {
            "spf_record": "v=spf1 include:sparkpostmail.com ~all",
            "spf_note": "Si usas SparkPost EU, el include es 'eu.sparkpostmail.com'.",
            "dkim_note": "SparkPost te genera la clave DKIM al añadir el sending domain. Publica el TXT en scph0625._domainkey.{domain} (el selector cambia por cuenta).",
            "dmarc_record": "v=DMARC1; p=none; rua=mailto:dmarc@{domain}",
            "guide_url": "https://support.sparkpost.com/docs/getting-started/setting-up-domains",
        },
    },
    "resend": {
        "label": "Resend (SMTP)", "host": "smtp.resend.com", "port": 587, "tls": True, "ssl": False, "kind": "smtp",
        "hint": "User: resend. Password: tu API key (re_...).",
        "dns": {
            "spf_record": "v=spf1 include:amazonses.com ~all",
            "spf_note": "Resend usa Amazon SES por debajo, así que el include de SPF es el de SES.",
            "dkim_note": "Resend → Domains → Add Domain te muestra 3 TXT a publicar (un SPF, un DKIM en resend._domainkey.{domain} y un MX para tracking).",
            "dmarc_record": "v=DMARC1; p=none; rua=mailto:dmarc@{domain}",
            "guide_url": "https://resend.com/docs/dashboard/domains/introduction",
        },
    },
    "brevo": {
        "label": "Brevo (API)", "kind": "api",
        "dns": {
            "spf_record": "v=spf1 include:spf.brevo.com ~all",
            "spf_note": "Brevo (antes Sendinblue) requiere verificar el dominio antes de poder enviar desde direcciones del mismo.",
            "dkim_note": "Brevo → Senders & IP → Domains → Authenticate. Te dan un TXT en mail._domainkey.{domain} (selector 'mail').",
            "dmarc_record": "v=DMARC1; p=none; rua=mailto:dmarc@{domain}",
            "guide_url": "https://help.brevo.com/hc/en-us/articles/12163873383186",
        },
    },
    "sendgrid": {
        "label": "SendGrid (API)", "kind": "api",
        "dns": {
            "spf_record": "v=spf1 include:sendgrid.net ~all",
            "spf_note": "Sin Domain Authentication tu correo se envía como 'sendgrid.net' y reduce la entregabilidad drásticamente.",
            "dkim_note": "SendGrid → Settings → Sender Authentication → Domain Authentication. Te genera 3 CNAMEs (s1._domainkey.{domain}, s2._domainkey.{domain} y un CNAME de tracking).",
            "dmarc_record": "v=DMARC1; p=none; rua=mailto:dmarc@{domain}",
            "guide_url": "https://docs.sendgrid.com/ui/account-and-settings/how-to-set-up-domain-authentication",
        },
    },
}


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(serializer.validated_data["current_password"]):
            return Response({"detail": "Contraseña actual incorrecta."}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(serializer.validated_data["new_password"])
        user.save()
        return Response({"detail": "Contraseña actualizada."})


# --- Admin-only: user management ----------------------------------------

class AdminUserListView(generics.ListCreateAPIView):
    permission_classes = (IsAdminUser,)
    queryset = User.objects.all().order_by("-date_joined")
    serializer_class = AdminUserSerializer


class AdminUserDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (IsAdminUser,)
    queryset = User.objects.all()
    serializer_class = AdminUserSerializer

    def destroy(self, request, *args, **kwargs):
        target = self.get_object()
        if target.id == request.user.id:
            return Response(
                {"detail": "No puedes eliminarte a ti mismo."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if target.is_staff and User.objects.filter(is_staff=True).count() <= 1:
            return Response(
                {"detail": "No puedes eliminar al último admin."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        target = self.get_object()
        if (
            target.is_staff
            and request.data.get("is_admin") is False
            and User.objects.filter(is_staff=True).count() <= 1
        ):
            return Response(
                {"detail": "No puedes quitar el rol admin al último admin."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)


# --- Admin-only: API keys for the external subscriber endpoint ----------

class ApiKeyListCreateView(generics.ListCreateAPIView):
    permission_classes = (IsAdminUser,)
    serializer_class = ApiKeySerializer
    queryset = ApiKey.objects.all()

    def create(self, request, *args, **kwargs):
        # Keys belong to the shared admin owner (data ownership stays via get_admin_user()).
        owner = get_admin_user() or request.user
        name = (request.data.get("name") or "").strip()[:100]
        key, raw = ApiKey.generate(user=owner, name=name)
        data = ApiKeySerializer(key).data
        data["key"] = raw  # shown ONCE; never retrievable again
        return Response(data, status=status.HTTP_201_CREATED)


class ApiKeyDetailView(generics.RetrieveDestroyAPIView):
    permission_classes = (IsAdminUser,)
    serializer_class = ApiKeySerializer
    queryset = ApiKey.objects.all()


# --- Admin-only: download SQLite database -------------------------------

@api_view(["GET"])
@permission_classes([IsAdminUser])
def db_export(request):
    db_path = settings.DATABASES["default"].get("NAME")
    if not db_path or not os.path.exists(db_path):
        raise Http404("Base de datos no encontrada o no es SQLite.")
    fname = f"mailerup-{slugify(request.user.username or 'backup')}.sqlite3"
    response = FileResponse(
        open(db_path, "rb"),
        as_attachment=True,
        filename=fname,
        content_type="application/octet-stream",
    )
    return response


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def email_providers(request):
    return Response([
        {"key": k, **v} for k, v in PROVIDER_PRESETS.items()
    ])


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def test_email(request):
    user = request.user
    to_addr = (request.data.get("to") or user.email or "").strip()
    if not to_addr:
        return Response({"detail": "Indica un email de destino."}, status=400)

    from apps.integrations.email_sender import (
        get_sender, NullSender, SMTPSender, BrevoSender, SendGridSender, EmailSendError,
    )

    sender = get_sender(user)

    if isinstance(sender, NullSender):
        return Response({
            "detail": (
                "No se ha enviado nada: tu proveedor es 'Local' o el SMTP/API no está "
                "configurado. Selecciona un proveedor en Ajustes, rellena las credenciales "
                "y guarda antes de probar."
            ),
        }, status=400)

    # SMTP credentials live in .env; check the value the sender was actually built with.
    smtp_user = getattr(sender, "user", "") if isinstance(sender, SMTPSender) else ""
    if isinstance(sender, SMTPSender) and sender.user and not getattr(sender, "password", ""):
        return Response({
            "detail": "Falta la contraseña SMTP. Introdúcela en Ajustes y guarda.",
        }, status=400)

    if isinstance(sender, BrevoSender) and not user.brevo_api_key:
        return Response({"detail": "Falta Brevo API key."}, status=400)
    if isinstance(sender, SendGridSender) and not user.sendgrid_api_key:
        return Response({"detail": "Falta SendGrid API key."}, status=400)

    from_addr = (user.from_email or smtp_user or "").strip()
    if not from_addr and isinstance(sender, SMTPSender):
        return Response({
            "detail": (
                "Falta el email del remitente. Configura 'Email del remitente' en Ajustes "
                "(o usa el mismo email del usuario SMTP)."
            ),
        }, status=400)

    warning = None
    if isinstance(sender, SMTPSender) and smtp_user and "@" in smtp_user:
        smtp_user_domain = smtp_user.split("@", 1)[1].lower()
        from_domain = from_addr.split("@", 1)[1].lower() if "@" in from_addr else ""
        if from_domain and smtp_user_domain and from_domain != smtp_user_domain:
            warning = (
                f"El From ({from_addr}) usa un dominio distinto del usuario SMTP "
                f"(@{smtp_user_domain}). Muchos servidores (incluido Raiola) aceptan "
                "el correo pero lo descartan en silencio. Usa un From del mismo dominio."
            )

    try:
        msg_id = sender.send(
            to_email=to_addr,
            to_name=user.username or "",
            from_name=user.from_name or user.username or "MailerUp",
            from_email=from_addr,
            subject="Prueba MailerUp",
            html="<p>Email de prueba enviado desde MailerUp.</p>",
        )
    except EmailSendError as exc:
        return Response({"detail": str(exc)}, status=400)
    except Exception as exc:
        return Response({"detail": f"Error inesperado: {exc.__class__.__name__}: {exc}"}, status=400)

    if not msg_id:
        return Response({"detail": "El proveedor no confirmó el envío."}, status=400)

    detail = (
        f"Email aceptado por el servidor SMTP y entregado a la cola "
        f"({from_addr} → {to_addr}). Si no llega a la bandeja de entrada, "
        f"revisa la carpeta de spam y los registros SPF/DKIM del dominio remitente."
    )
    payload = {
        "detail": detail,
        "message_id": msg_id,
        "provider": user.email_provider,
        "from": from_addr,
        "to": to_addr,
    }
    if warning:
        payload["warning"] = warning
    return Response(payload)


# --- Cookie-based JWT auth --------------------------------------------------

def _set_token_cookies(response, access_token, refresh_token=None):
    """Helper: set HttpOnly, SameSite=Lax JWT cookies."""
    secure = not settings.DEBUG
    response.set_cookie(
        'access',
        str(access_token),
        max_age=int(settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds()),
        httponly=True,
        samesite='Lax',
        secure=secure,
        path='/',
    )
    if refresh_token is not None:
        response.set_cookie(
            'refresh',
            str(refresh_token),
            max_age=int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()),
            httponly=True,
            samesite='Lax',
            secure=secure,
            path='/',
        )


class CookieTokenObtainView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "login"

    def post(self, request):
        from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
        from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken
        from rest_framework.exceptions import ValidationError as DRFValidationError

        serializer = TokenObtainPairSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except (AuthenticationFailed, InvalidToken, DRFValidationError):
            return Response({'detail': 'Credenciales incorrectas.'}, status=status.HTTP_401_UNAUTHORIZED)
        data = serializer.validated_data
        response = Response({'detail': 'ok'})
        _set_token_cookies(response, data['access'], data['refresh'])
        return response


class CookieTokenRefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.COOKIES.get('refresh')
        if not refresh_token:
            return Response({'detail': 'No hay sesión activa.'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            token = RefreshToken(refresh_token)
            access = token.access_token
            new_refresh = token if settings.SIMPLE_JWT.get('ROTATE_REFRESH_TOKENS') else None
            response = Response({'detail': 'ok'})
            _set_token_cookies(response, access, new_refresh)
            return response
        except Exception:
            response = Response({'detail': 'Sesión caducada.'}, status=status.HTTP_401_UNAUTHORIZED)
            response.delete_cookie('access')
            response.delete_cookie('refresh')
            return response


class CookieTokenLogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # Invalida el refresh token en el servidor (blacklist), no solo borra la
        # cookie: si el token se hubiera capturado antes del logout, deja de servir.
        refresh_token = request.COOKIES.get('refresh')
        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except Exception:
                pass  # token ya inválido/caducado: nada que invalidar
        response = Response({'detail': 'Sesión cerrada.'})
        response.delete_cookie('access', path='/')
        response.delete_cookie('refresh', path='/')
        return response
