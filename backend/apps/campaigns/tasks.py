import hashlib
import logging
import re
from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def send_campaign(campaign_id):
    """Compatibility shim.

    Historically this task sent the whole campaign inline. Sending is now done
    progressively, in small batches, by the in-process scheduler
    (``process_sending_campaigns``). All this does is flip the campaign into the
    ``sending`` state; the scheduler picks it up and drips it out at a controlled
    rate. Kept as a Celery task so any legacy ``.delay()`` call still works.
    """
    from .models import Campaign

    try:
        campaign = Campaign.objects.get(pk=campaign_id)
    except Campaign.DoesNotExist:
        return
    if campaign.status in ("draft", "scheduled"):
        campaign.status = "sending"
        campaign.save(update_fields=["status"])


def _variant_for(campaign, subscriber):
    """Deterministic A/B variant for a subscriber.

    Uses a stable hash of (campaign, subscriber) so the assignment is identical
    across send batches and process restarts — no need to materialise the whole
    recipient list up front. Over a large list the distribution approaches
    ``ab_split_percent`` for A and the remainder for B.
    """
    if not (campaign.ab_enabled and campaign.subject_b.strip()):
        return ""
    digest = hashlib.md5(f"{campaign.id}:{subscriber.id}".encode()).hexdigest()
    bucket = int(digest[:8], 16) % 100
    return "A" if bucket < campaign.ab_split_percent else "B"


def _deliver(campaign, sender, subscriber):
    """Send one email and record the CampaignSend. Returns True if a new send
    was attempted, False if it was already sent (claimed by another worker)."""
    from .models import CampaignSend

    # Claim the recipient first so concurrent schedulers (e.g. multiple workers)
    # never send the same email twice — unique_together(campaign, subscriber).
    send, created = CampaignSend.objects.get_or_create(
        campaign=campaign, subscriber=subscriber
    )
    if not created:
        return False

    variant = _variant_for(campaign, subscriber)
    raw_subject = campaign.subject_b if variant == "B" else campaign.subject
    # Personaliza el asunto igual que el cuerpo (first_name/last_name/email).
    subject = (
        (raw_subject or "")
        .replace("{{first_name}}", subscriber.first_name)
        .replace("{{last_name}}", subscriber.last_name)
        .replace("{{email}}", subscriber.email)
    )
    # URL de baja en un clic (RFC 8058) para la cabecera List-Unsubscribe.
    # Mismo token/endpoint que el enlace del pie, así una baja por el botón del
    # cliente de correo o por el enlace del cuerpo son equivalentes.
    from apps.analytics.views import make_unsubscribe_token
    unsub_url = (
        f"{settings.PUBLIC_BASE_URL.rstrip('/')}/u/"
        f"{make_unsubscribe_token(subscriber.id, campaign.id)}/"
    )
    try:
        msg_id = sender.send(
            to_email=subscriber.email,
            to_name=f"{subscriber.first_name} {subscriber.last_name}".strip(),
            from_name=campaign.from_name,
            from_email=campaign.from_email,
            subject=subject,
            html=_personalize(campaign.html_content, subscriber, campaign),
            campaign_id=str(campaign.id),
            subscriber_id=str(subscriber.id),
            list_unsubscribe_url=unsub_url,
        )
    except Exception as exc:
        logger.exception(
            "Error sending campaign %s to subscriber %s: %s",
            campaign.id, subscriber.id, exc,
        )
        msg_id = f"error: {exc}"

    send.provider_message_id = (msg_id or "")[:255]
    send.ab_variant = variant
    send.save(update_fields=["provider_message_id", "ab_variant"])
    return True


def _pending_subscribers(campaign):
    """Active subscribers of the campaign scope (a single group, or ALL groups
    when ``send_to_all``) that have not been sent to yet and are not excluded."""
    from .models import CampaignSend
    from apps.subscribers.models import Subscriber

    excluded = set(filter(None, (
        e.strip().lower() for e in campaign.excluded_emails.splitlines()
    )))
    already = CampaignSend.objects.filter(campaign=campaign).values("subscriber_id")
    # Nunca enviar campañas a quien esté actualmente DENTRO de una automatización
    # (enrolamiento activo): evita el doble envío mientras recibe la secuencia.
    from apps.automations.models import AutomationEnrollment
    in_automation = AutomationEnrollment.objects.filter(
        status="active", automation__user=campaign.user
    ).values("subscriber_id")

    if campaign.send_to_all:
        qs = Subscriber.objects.filter(list__user=campaign.user, status="active")
    else:
        qs = Subscriber.objects.filter(list=campaign.subscriber_list, status="active")
    qs = qs.exclude(id__in=already).exclude(id__in=in_automation)
    if excluded:
        # Subscriber emails are normalised to lowercase on entry (add/import),
        # so a lowercase __in match is correct.
        qs = qs.exclude(email__in=excluded)

    if campaign.send_to_all:
        # Una persona puede estar en varios grupos: enviamos UN solo correo por
        # email. Descartamos los emails ya enviados en esta campaña (entre tandas)
        # y deduplicamos por email con DISTINCT ON (Postgres).
        already_emails = set(
            e for e in CampaignSend.objects.filter(campaign=campaign)
            .values_list("subscriber__email", flat=True) if e
        )
        if already_emails:
            qs = qs.exclude(email__in=already_emails)
        return qs.order_by("email", "subscribed_at").distinct("email")
    return qs.order_by("subscribed_at")


def _finalize(campaign):
    """Mark a fully-processed campaign as sent (or failed if every send errored)."""
    from .models import CampaignSend

    total = CampaignSend.objects.filter(campaign=campaign).count()
    errors = CampaignSend.objects.filter(
        campaign=campaign, provider_message_id__startswith="error:"
    ).count()
    campaign.status = "failed" if total > 0 and errors == total else "sent"
    campaign.sent_at = timezone.now()
    campaign.save(update_fields=["status", "sent_at"])
    logger.info(
        "Campaign %s finalised: status=%s sent=%s errors=%s",
        campaign.id, campaign.status, total, errors,
    )


def process_sending_campaigns(budget):
    """Send up to ``budget`` emails across all campaigns currently in the
    ``sending`` state, then return.

    This is the heart of progressive sending: the scheduler calls it on every
    tick with a bounded budget, so a list of thousands is spread over many ticks
    instead of going out in one burst that would trip provider rate limits.
    State lives entirely in the DB (CampaignSend rows), so it resumes cleanly
    after a restart.
    """
    from .models import Campaign
    from apps.integrations.email_sender import get_sender

    if budget <= 0:
        return 0

    remaining = budget
    sent_count = 0
    for campaign in Campaign.objects.filter(status="sending").order_by("created_at"):
        if remaining <= 0:
            break
        batch = list(_pending_subscribers(campaign)[:remaining])
        if not batch:
            _finalize(campaign)
            continue
        sender = get_sender(campaign.user)
        for subscriber in batch:
            if remaining <= 0:
                break
            if _deliver(campaign, sender, subscriber):
                sent_count += 1
            remaining -= 1
        # If we drained this campaign within budget, finalise it right away so
        # its status flips to "sent" without waiting for the next tick.
        if remaining > 0 and not _pending_subscribers(campaign).exists():
            _finalize(campaign)
    return sent_count


HREF_RE = re.compile(r'href="([^"]+)"', re.IGNORECASE)


def _personalize(html, subscriber, campaign):
    """Substitute placeholders, rewrite links for click tracking, inject open pixel."""
    from apps.analytics.views import make_unsubscribe_token, make_track_token
    from apps.accounts.footer import apply_footer, inject_before_body_end
    from django.utils.html import escape

    base = settings.PUBLIC_BASE_URL.rstrip("/")
    unsub_token = make_unsubscribe_token(subscriber.id, campaign.id)
    open_token = make_track_token(campaign.id, subscriber.id)
    unsub_url = f"{base}/u/{unsub_token}/"

    # Pie SIEMPRE generado al enviar desde la config (quita cualquier pie del
    # cuerpo y añade uno limpio y bien estilado). Garantiza color/enlaces y evita
    # duplicados pase lo que pase con el editor. El {{unsubscribe_url}} del pie se
    # resuelve en el .replace de abajo.
    html = apply_footer(html, campaign.user)

    # Escapamos los datos del suscriptor: first_name/last_name/email llegan del
    # formulario público de alta sin sanear, y aquí se insertan en HTML que se
    # envía como correo. Sin escapar, un tercero podría inyectar HTML/markup en
    # los correos del remitente (phishing/spoofing) suscribiéndose con un nombre
    # malicioso. El cuerpo de la campaña (autoría del admin) NO se escapa.
    html = (
        html
        .replace("{{first_name}}", escape(subscriber.first_name))
        .replace("{{last_name}}", escape(subscriber.last_name))
        .replace("{{email}}", escape(subscriber.email))
        .replace("{{unsubscribe_url}}", unsub_url)
    )

    def rewrite(match):
        url = match.group(1)
        if url.startswith(("mailto:", "tel:", "#")) or url == unsub_url:
            return match.group(0)
        # El destino va firmado DENTRO del token (no en `?u=`): un token
        # válido para un enlace no sirve para redirigir a otro destino.
        click_token = make_track_token(campaign.id, subscriber.id, url)
        return f'href="{base}/c/{click_token}/"'

    html = HREF_RE.sub(rewrite, html)

    pixel = f'<img src="{base}/o/{open_token}/" width="1" height="1" alt="" style="display:block;border:0;outline:none" />'
    # En correos de modo HTML (documento completo) el pixel se inserta antes de
    # </body> para no quedar fuera del documento tras </html>.
    return inject_before_body_end(html, pixel)
