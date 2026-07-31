"""Ingesta de rebotes (NDR) desde el buzón local de bounces.

`bounces@` tiene su propio Maildir en el mismo servidor (ver
/etc/postfix/vmailbox), así que leemos los ficheros directamente del disco en
vez de montar un cliente IMAP. Cada NDR es un DSN estándar (RFC 3464):
multipart/report con una parte message/delivery-status que trae
Final-Recipient/Action/Status por destinatario.

No hay forma de saber a qué campaña pertenecía un rebote (el NDR solo trae el
email) — se atribuye best-effort al CampaignSend más reciente de ese
suscriptor. Un rebote dominio 5.x.x (hard) marca al suscriptor como
'bounced' para dejar de enviarle; 4.x.x (soft) solo se registra.
"""
import email
import logging
import os
from email.policy import default as _default_policy

from django.conf import settings

logger = logging.getLogger(__name__)


def _iter_maildir_files(maildir_path):
    for sub in ("new", "cur"):
        d = os.path.join(maildir_path, sub)
        if not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            path = os.path.join(d, name)
            if os.path.isfile(path):
                yield path


def _parse_dsn(raw_bytes):
    """Extrae (email, action, status, motivo) del primer bloque per-recipient
    de un DSN. Devuelve None si el mensaje no es un delivery-status report."""
    msg = email.message_from_bytes(raw_bytes, policy=_default_policy)
    if not msg.is_multipart():
        return None
    for part in msg.walk():
        if part.get_content_type() != "message/delivery-status":
            continue
        payload = part.get_payload()
        blocks = payload if isinstance(payload, list) else [part]
        # El primer bloque son campos del mensaje (Reporting-MTA); los
        # siguientes son por destinatario (Final-Recipient/Action/Status).
        for block in blocks:
            final_recipient = (block.get("Final-Recipient") or "").strip()
            action = (block.get("Action") or "").strip().lower()
            if not final_recipient or not action:
                continue
            if ";" in final_recipient:
                final_recipient = final_recipient.split(";", 1)[1].strip()
            status = (block.get("Status") or "").strip()
            diag = (block.get("Diagnostic-Code") or "").strip()
            return final_recipient.strip("<>").lower(), action, status, diag
    return None


def process_bounce_mailbox():
    """Procesa los NDR pendientes en BOUNCE_MAILDIR_PATH. Devuelve cuántos se
    han registrado como rebote. No-op si no hay ruta configurada."""
    from apps.subscribers.models import Subscriber
    from apps.campaigns.models import CampaignSend
    from .models import EmailBounce

    maildir = getattr(settings, "BOUNCE_MAILDIR_PATH", "") or ""
    if not maildir or not os.path.isdir(maildir):
        return 0

    processed = 0
    for path in _iter_maildir_files(maildir):
        try:
            with open(path, "rb") as fh:
                raw = fh.read()
            parsed = _parse_dsn(raw)
            if parsed is None:
                os.remove(path)  # no es un DSN reconocible
                continue

            addr, action, status, diag = parsed
            if action != "failed":
                # "delayed"/"relayed"/"expanded": no es un rebote definitivo.
                os.remove(path)
                continue

            subs = list(Subscriber.objects.filter(email__iexact=addr))
            if not subs:
                os.remove(path)
                continue

            bounce_type = "hard" if status.startswith("5") else "soft"
            reason = (diag or status or "")[:500]
            for sub in subs:
                last_send = (
                    CampaignSend.objects.filter(subscriber=sub)
                    .order_by("-sent_at").first()
                )
                EmailBounce.objects.create(
                    campaign=last_send.campaign if last_send else None,
                    subscriber=sub,
                    bounce_type=bounce_type,
                    reason=reason,
                )
                if bounce_type == "hard" and sub.status == "active":
                    sub.status = "bounced"
                    sub.save(update_fields=["status"])
            os.remove(path)
            processed += 1
        except Exception:
            logger.exception("Error procesando rebote %s", path)
            # No se borra: se reintenta en el siguiente tick.
    return processed
