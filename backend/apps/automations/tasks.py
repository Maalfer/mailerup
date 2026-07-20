import logging
from celery import shared_task
from django.utils import timezone

from apps.forms.models import SubscriptionForm
from apps.subscribers.models import Subscriber
from .models import Automation, AutomationEnrollment, AutomationStep, AutomationSend

logger = logging.getLogger(__name__)


@shared_task
def trigger_automation_for_subscriber(subscriber_id, form_id):
    """
    Llamada cuando alguien verifica su suscripción a través de un formulario.
    Busca la automatización asociada al formulario y enrola al suscriptor.
    """

    try:
        form = SubscriptionForm.objects.select_related("automation").get(pk=form_id)
    except SubscriptionForm.DoesNotExist:
        return

    if not hasattr(form, "automation") or form.automation is None:
        return

    automation = form.automation
    if not automation.is_active:
        return

    try:
        subscriber = Subscriber.objects.get(pk=subscriber_id)
    except Subscriber.DoesNotExist:
        return

    enrollment, created = AutomationEnrollment.objects.get_or_create(
        automation=automation,
        subscriber=subscriber,
        defaults={"status": "active"},
    )
    if not created:
        return  # ya estaba enrolado

    # Programar el primer paso
    process_automation_queue.delay()


@shared_task
def process_automation_queue():
    """
    Corre periódicamente (o se llama tras un enrolamiento).
    Envía los pasos de automatización que ya deben haberse enviado.
    """
    import re
    from urllib.parse import quote
    from apps.integrations.email_sender import get_sender, smtp_config_from_env
    from apps.analytics.views import make_unsubscribe_token, make_auto_track_token
    from django.conf import settings

    href_re = re.compile(r'href="([^"]+)"', re.IGNORECASE)

    base = settings.PUBLIC_BASE_URL.rstrip("/")
    now = timezone.now()
    # subscriber__status="active": red de seguridad. Si el suscriptor se dio de
    # baja (o rebotó/quejó) mientras la matrícula seguía activa, no debe
    # seguir recibiendo los pasos pendientes de la secuencia.
    active_enrollments = AutomationEnrollment.objects.filter(
        status="active", subscriber__status="active"
    ).select_related("automation", "automation__user", "subscriber")

    for enrollment in active_enrollments:
        automation = enrollment.automation
        if not automation.is_active:
            continue

        steps = list(automation.steps.order_by("order"))
        if not steps:
            enrollment.status = "completed"
            enrollment.save(update_fields=["status"])
            continue

        for step in steps:
            if step.order <= enrollment.last_step_sent:
                continue  # ya enviado

            # Calcular si ya es hora de enviarlo
            send_after = enrollment.enrolled_at + timezone.timedelta(hours=step.delay_hours())
            if now < send_after:
                break  # este y los siguientes aún no toca

            # Verificar que no se haya enviado ya
            if AutomationSend.objects.filter(enrollment=enrollment, step=step).exists():
                enrollment.last_step_sent = step.order
                enrollment.save(update_fields=["last_step_sent"])
                continue

            # Enviar
            subscriber = enrollment.subscriber
            user = automation.user
            sender = get_sender(user)
            smtp_cfg = smtp_config_from_env() or {}
            from_name = step.from_name or user.from_name or ""
            from_email = step.from_email or user.from_email or smtp_cfg.get("user") or user.email

            # Enlace de baja firmado (cumplimiento legal: toda la secuencia debe
            # permitir darse de baja). El token solo necesita el subscriber_id.
            unsub_url = f"{base}/u/{make_unsubscribe_token(subscriber.id)}/"

            from django.utils.html import escape

            def _fill(text, html=False):
                # En cuerpo HTML escapamos los datos del suscriptor (vienen del alta
                # pública sin sanear) para que nadie inyecte markup en el correo del
                # remitente. En el asunto (texto plano) no se escapa.
                fn, ln, em = subscriber.first_name, subscriber.last_name, subscriber.email
                if html:
                    fn, ln, em = escape(fn), escape(ln), escape(em)
                return (
                    (text or "")
                    .replace("{{first_name}}", fn)
                    .replace("{{last_name}}", ln)
                    .replace("{{email}}", em)
                    .replace("{{unsubscribe_url}}", unsub_url)
                )

            # Personaliza también el ASUNTO (antes salía "{{first_name}}" literal).
            subject = _fill(step.subject)
            # Pie SIEMPRE generado al enviar desde la config (quita el del cuerpo
            # y añade uno limpio), luego se rellenan placeholders.
            from apps.accounts.footer import apply_footer, inject_before_body_end
            html = _fill(apply_footer(step.html_content, user), html=True)

            # Tracking de automatización: reescribe enlaces a /ca/<token>/ e
            # inyecta el pixel de apertura /oa/<token>/ (espeja el de campañas).
            track_token = make_auto_track_token(step.id, subscriber.id)

            def _rewrite(match, _unsub=unsub_url, _tok=track_token):
                u = match.group(1)
                if u.startswith(("mailto:", "tel:", "#")) or u == _unsub:
                    return match.group(0)
                return f'href="{base}/ca/{_tok}/?u={quote(u, safe="")}"'

            html = href_re.sub(_rewrite, html)
            html = inject_before_body_end(
                html,
                f'<img src="{base}/oa/{track_token}/" width="1" height="1" '
                f'alt="" style="display:block;border:0;outline:none" />'
            )

            try:
                msg_id = sender.send(
                    to_email=subscriber.email,
                    to_name=f"{subscriber.first_name} {subscriber.last_name}".strip(),
                    from_name=from_name,
                    from_email=from_email,
                    subject=subject,
                    html=html,
                    campaign_id=None,
                    subscriber_id=str(subscriber.id),
                )
            except Exception:
                logger.exception("Error sending automation step %s to %s", step.id, subscriber.email)
                # No marcamos el paso como enviado: no creamos AutomationSend ni
                # avanzamos last_step_sent. Así el scheduler lo reintenta en la
                # próxima vuelta en lugar de dar por enviado un correo que falló.
                # break para no adelantar pasos posteriores de esta secuencia.
                break

            AutomationSend.objects.create(
                enrollment=enrollment,
                step=step,
                provider_message_id=msg_id or "",
            )
            enrollment.last_step_sent = step.order
            enrollment.save(update_fields=["last_step_sent"])

        # Comprobar si todos los pasos han sido enviados
        all_orders = {s.order for s in steps}
        sent_orders = set(
            AutomationSend.objects.filter(enrollment=enrollment)
            .values_list("step__order", flat=True)
        )
        if all_orders.issubset(sent_orders):
            enrollment.status = "completed"
            enrollment.save(update_fields=["status"])
