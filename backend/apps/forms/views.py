import logging
import re
from django.core import signing
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils.html import escape
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SubscriptionForm
from .serializers import SubscriptionFormSerializer

logger = logging.getLogger(__name__)

SUBSCRIPTION_CONFIRM_SALT = "mailerup.subscription.confirm.v1"


def make_subscription_token(email, form_id, first_name="", last_name=""):
    return signing.dumps(
        {"e": email, "f": str(form_id), "fn": first_name, "ln": last_name},
        salt=SUBSCRIPTION_CONFIRM_SALT,
        compress=True,
    )


def parse_subscription_token(token, max_age_hours=48):
    return signing.loads(
        token, salt=SUBSCRIPTION_CONFIRM_SALT, max_age=60 * 60 * max_age_hours
    )


# ---------------------------------------------------------------------------
# Shared HTML page template (same style as unsubscribe page)
# ---------------------------------------------------------------------------

FORM_PAGE = """<!doctype html>
<html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
body{{font-family:system-ui,-apple-system,sans-serif;background:#f8fafc;color:#0f172a;margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:1rem}}
.card{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:2.5rem;max-width:480px;width:100%;text-align:center}}
h1{{margin:0 0 0.5rem;font-size:1.5rem}}.ico{{font-size:3rem;margin-bottom:0.5rem}}
p{{color:#475569;line-height:1.5;margin:0.5rem 0}}.email{{font-family:monospace;background:#f1f5f9;padding:2px 6px;border-radius:4px}}
.muted{{color:#94a3b8;font-size:.875rem;margin-top:1.5rem}}
</style></head><body><div class="card">{body}</div></body></html>"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _safe_color(value, default="#2563eb"):
    """Solo se admite un color hex (#rgb / #rrggbb). Cualquier otra cosa
    (controlable por el usuario que crea el formulario) se descarta para que no
    pueda romper el atributo style e inyectar CSS/HTML donde se pegue el embed."""
    value = (value or "").strip()
    return value if _HEX_COLOR_RE.match(value) else default


def _build_embed_html(form, base):
    # title/description/button_text los controla quien crea el formulario y este
    # HTML se incrusta tal cual en sitios externos: escapar para evitar stored XSS.
    color = _safe_color(form.primary_color)
    safe_title = escape(form.title)
    safe_button = escape(form.button_text)
    fields_html = ""
    if form.collect_first_name:
        fields_html += '<div style="margin-bottom:12px"><input type="text" name="first_name" placeholder="Tu nombre" style="width:100%;padding:10px 14px;border:1px solid #d1d5db;border-radius:6px;font-size:14px;box-sizing:border-box" /></div>'
    if form.collect_last_name:
        fields_html += '<div style="margin-bottom:12px"><input type="text" name="last_name" placeholder="Tus apellidos" style="width:100%;padding:10px 14px;border:1px solid #d1d5db;border-radius:6px;font-size:14px;box-sizing:border-box" /></div>'
    desc_html = f'<p style="color:#6b7280;font-size:14px;margin:0 0 16px 0">{escape(form.description)}</p>' if form.description else ""

    return f"""<!-- Mailerup Form: {escape(form.name)} -->
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:28px;max-width:440px">
  <h3 style="margin:0 0 8px 0;font-size:20px;font-weight:600;color:#111827">{safe_title}</h3>
  {desc_html}
  <form action="{base}/subscribe/{form.id}/" method="post">
    <input type="text" name="website" style="display:none" tabindex="-1" autocomplete="off" />
    {fields_html}
    <div style="margin-bottom:16px">
      <input type="email" name="email" placeholder="tu@email.com" required
             style="width:100%;padding:10px 14px;border:1px solid #d1d5db;border-radius:6px;font-size:14px;box-sizing:border-box" />
    </div>
    <button type="submit"
            style="width:100%;padding:11px 20px;background:{color};color:#fff;border:none;border-radius:6px;font-size:15px;font-weight:500;cursor:pointer">
      {safe_button}
    </button>
  </form>
</div>"""


def _verification_email_html(form_obj, greeting, verify_url):
    """Returns the HTML body for the double-opt-in verification email.

    `greeting` must already be HTML-escaped by the caller (it embeds the
    unauthenticated subscriber-supplied first_name); form_obj.title and
    primary_color are form-owner-controlled but escaped/validated here too,
    same as _build_embed_html, since this HTML is emailed out verbatim.
    """
    safe_title = escape(form_obj.title)
    color = _safe_color(form_obj.primary_color)
    return f"""<!doctype html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f8fafc;margin:0;padding:20px">
<div style="max-width:520px;margin:0 auto;background:#fff;border-radius:12px;padding:36px;border:1px solid #e2e8f0">
  <h2 style="margin:0 0 8px;color:#111827">{safe_title}</h2>
  <p style="color:#374151;margin:0 0 24px">{greeting} Por favor confirma tu suscripcion haciendo clic en el boton:</p>
  <p style="text-align:center;margin:0 0 24px">
    <a href="{verify_url}" style="display:inline-block;padding:12px 28px;background:{color};color:#fff;text-decoration:none;border-radius:8px;font-weight:600;font-size:15px">
      Confirmar suscripcion
    </a>
  </p>
  <p style="color:#6b7280;font-size:13px;margin:0">Si no has solicitado esta suscripcion, ignora este correo. El enlace caduca en 48 horas.</p>
</div>
</body></html>"""


def _send_verification_email(form_obj, email, first_name, verify_url):
    from apps.integrations.email_sender import get_sender

    from_email = (
        form_obj.user.from_email
        or getattr(form_obj.user, "smtp_user", None)
        or form_obj.user.email
        or ""
    )
    if not from_email:
        logger.warning(
            "No from_email configured for user %s, skipping verification email",
            form_obj.user.id,
        )
        return

    sender = get_sender(form_obj.user)
    safe_first_name = escape(first_name)
    greeting = f"Hola {safe_first_name}," if safe_first_name else "Hola,"
    html = _verification_email_html(form_obj, greeting, verify_url)

    try:
        sender.send(
            to_email=email,
            to_name=first_name,
            from_name=form_obj.user.from_name or "Newsletter",
            from_email=from_email,
            subject="Confirma tu suscripción para recibir el recurso de ciberseguridad",
            html=html,
            campaign_id=None,
            subscriber_id=None,
        )
    except Exception:
        logger.exception("Error sending verification email to %s for form %s", email, form_obj.id)


# ---------------------------------------------------------------------------
# Authenticated ViewSet (CRUD + embed)
# ---------------------------------------------------------------------------

class SubscriptionFormViewSet(viewsets.ModelViewSet):
    serializer_class = SubscriptionFormSerializer

    def get_queryset(self):
        from apps.accounts.serializers import get_admin_user
        return SubscriptionForm.objects.filter(user=get_admin_user() or self.request.user)

    def perform_create(self, serializer):
        from apps.accounts.serializers import get_admin_user
        serializer.save(user=get_admin_user() or self.request.user)

    @action(detail=True, methods=["get"])
    def embed(self, request, pk=None):
        """Returns the HTML snippet to embed in external websites."""
        form = self.get_object()
        base = settings.PUBLIC_BASE_URL.rstrip("/")
        html = _build_embed_html(form, base)
        return Response({"html": html, "url": f"{base}/subscribe/{form.id}/"})


# ---------------------------------------------------------------------------
# Public views (no authentication required)
# ---------------------------------------------------------------------------

class SubscribeView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "subscribe"

    def post(self, request, form_id):
        # Honeypot: if the hidden website field is filled, silently ignore
        if request.data.get("website") or request.POST.get("website"):
            return HttpResponse(FORM_PAGE.format(
                title="Revisa tu correo para recibir el recurso",
                body='<div class="ico">&#x1F4E9;</div><h1>¡Ya casi está!</h1><p>Confirma tu correo desde el email que te hemos enviado y recibirás el recurso en tu bandeja en unos minutos.</p>'
            ))

        form_obj = get_object_or_404(SubscriptionForm, pk=form_id, is_active=True)

        # Support both JSON and form data
        if request.content_type and "application/json" in request.content_type:
            data = request.data
        else:
            data = request.POST

        email = (data.get("email") or "").strip().lower()
        first_name = (data.get("first_name") or "").strip()[:100]
        last_name = (data.get("last_name") or "").strip()[:100]

        if not email or "@" not in email:
            return HttpResponse(FORM_PAGE.format(
                title="Email invalido",
                body='<div class="ico">&#x26A0;&#xFE0F;</div><h1>Email invalido</h1><p>Por favor introduce una direccion de correo valida.</p>'
            ), status=400)

        # Check if already an active subscriber
        from apps.subscribers.views import _get_or_create_default_list
        from apps.subscribers.models import Subscriber

        lst = form_obj.target_list or _get_or_create_default_list(form_obj.user)
        existing = Subscriber.objects.filter(list=lst, email=email, status="active").first()
        if existing:
            return HttpResponse(FORM_PAGE.format(
                title="Ya suscrito",
                body=f'<div class="ico">&#x2705;</div><h1>Ya estas suscrito</h1><p>El correo <span class="email">{escape(email)}</span> ya forma parte de esta newsletter.</p>'
            ))

        # Generate token and send verification email
        token = make_subscription_token(email, form_obj.id, first_name, last_name)
        base = settings.PUBLIC_BASE_URL.rstrip("/")
        verify_url = f"{base}/verify-subscription/{token}/"

        _send_verification_email(form_obj, email, first_name, verify_url)

        # Escapa los datos del formulario (entrada pública reflejada en HTML).
        safe_email = escape(email)
        safe_name = escape(first_name)
        greeting = f"¡Ya casi está, {safe_name}!" if safe_name else "¡Ya casi está!"
        body = (
            '<div class="ico">&#x1F4E9;</div>'
            f'<h1>{greeting}</h1>'
            '<p>Para enviarte el recurso solo queda <strong>un último paso</strong>: confirmar tu correo.</p>'
            f'<p>Te acabamos de enviar un email a <span class="email">{safe_email}</span>. '
            'Ábrelo y pulsa el botón de confirmación y, en cuanto lo hagas, '
            '<strong>recibirás el recurso en tu bandeja de entrada en unos minutos</strong>.</p>'
            '<p class="muted">¿No lo ves? Revisa la carpeta de spam o promociones. El enlace caduca en 48 horas.</p>'
        )
        return HttpResponse(FORM_PAGE.format(title="Revisa tu correo para recibir el recurso", body=body))


class VerifySubscriptionView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, token):
        try:
            data = parse_subscription_token(token)
        except signing.SignatureExpired:
            body = '<div class="ico">&#x23F0;</div><h1>Enlace caducado</h1><p>El enlace de confirmacion ha caducado (48h). Vuelve a rellenar el formulario para recibir uno nuevo.</p>'
            return HttpResponse(FORM_PAGE.format(title="Enlace caducado", body=body), status=400)
        except signing.BadSignature:
            body = '<div class="ico">&#x26A0;&#xFE0F;</div><h1>Enlace invalido</h1><p>Este enlace no es valido.</p>'
            return HttpResponse(FORM_PAGE.format(title="Enlace invalido", body=body), status=400)

        try:
            form_obj = SubscriptionForm.objects.get(pk=data["f"])
        except SubscriptionForm.DoesNotExist:
            body = '<div class="ico">&#x26A0;&#xFE0F;</div><h1>Formulario no encontrado</h1>'
            return HttpResponse(FORM_PAGE.format(title="Error", body=body), status=404)

        from apps.subscribers.views import _get_or_create_default_list
        from apps.subscribers.models import Subscriber

        email = data["e"]
        first_name = data.get("fn", "")
        last_name = data.get("ln", "")

        lst = form_obj.target_list or _get_or_create_default_list(form_obj.user)
        subscriber, created = Subscriber.objects.get_or_create(
            list=lst,
            email=email,
            defaults={"first_name": first_name, "last_name": last_name, "status": "active"},
        )
        if not created and subscriber.status != "active":
            subscriber.status = "active"
            subscriber.save(update_fields=["status"])

        # Trigger automations if available (dynamic import to avoid circular imports)
        try:
            from apps.automations.tasks import trigger_automation_for_subscriber
            trigger_automation_for_subscriber.delay(str(subscriber.id), str(form_obj.id))
        except Exception:
            pass  # automations app may not be available yet

        # Escapar valores controlados por el usuario antes de interpolarlos en HTML
        # (success_message es editable por cualquier usuario autenticado → stored XSS).
        success_msg = escape(form_obj.success_message)
        safe_email = escape(email)
        body = f'<div class="ico">&#x1F389;</div><h1>Suscripcion confirmada!</h1><p>{success_msg}</p><p><span class="email">{safe_email}</span></p>'

        if form_obj.redirect_url:
            # Solo redirigir a http/https. Bloquea esquemas peligrosos
            # (javascript:, data:) y URLs scheme-relative (//evil.com) para que
            # el endpoint público no se use como redirector de phishing.
            from urllib.parse import urlparse
            if urlparse(form_obj.redirect_url).scheme in ("http", "https"):
                return HttpResponseRedirect(form_obj.redirect_url)

        return HttpResponse(FORM_PAGE.format(title="Suscrito!", body=body))
