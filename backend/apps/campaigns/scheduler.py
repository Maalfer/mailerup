"""Background thread that drives scheduled and progressive campaign sending.

Pragmatic single-process scheduler: a daemon thread wakes every ``TICK_SECONDS``
and on each tick it

  1. promotes due scheduled campaigns to the ``sending`` state,
  2. sends a bounded budget of emails across all ``sending`` campaigns so large
     lists drip out at a controlled rate, and
  3. periodically advances automation drips.

El ritmo (correos/hora) lo configura el admin desde Ajustes
(``User.send_rate_per_hour``) y se lee EN CALIENTE en cada tick: cambiarlo aplica
sin reiniciar. Un acumulador (token-bucket simple) reparte la tasa suavemente y
soporta tasas fraccionarias por tick.

Good enough for self-hosted setups without a Celery worker or Redis. For
horizontal scaling, run the web workers with MAILERUP_DISABLE_SCHEDULER=1 and a
single dedicated scheduler process.
"""
import logging
import threading
import time

from django.conf import settings

log = logging.getLogger(__name__)

# Resolución del tick (cada cuánto despierta el hilo). El ritmo real lo marca
# send_rate_per_hour; el tick solo define cómo de fino se reparte.
TICK_SECONDS = getattr(settings, "CAMPAIGN_SEND_INTERVAL_SECONDS", 15)
# Tasa por defecto (correos/hora) si no hay admin o el campo viene vacío.
DEFAULT_RATE_PER_HOUR = getattr(settings, "CAMPAIGN_SEND_RATE_PER_HOUR", 300)
AUTOMATION_EVERY_SECONDS = 60

_allowance = 0.0  # "tokens" acumulados (correos que ya podemos enviar)


def _get_rate_per_hour():
    """Correos/hora configurados por el admin (Ajustes). Se lee en cada tick."""
    try:
        from apps.accounts.serializers import get_admin_user
        admin = get_admin_user()
        rate = getattr(admin, "send_rate_per_hour", None) if admin else None
        if rate:
            return max(1, int(rate))
    except Exception:
        log.exception("No se pudo leer send_rate_per_hour; uso el valor por defecto")
    return max(1, int(DEFAULT_RATE_PER_HOUR))


def _promote_due_scheduled():
    """Flip scheduled campaigns whose time has come into the sending state."""
    from django.utils import timezone
    from .models import Campaign

    now = timezone.now()
    due = Campaign.objects.filter(status="scheduled", scheduled_at__lte=now)
    for campaign in due:
        log.info("Scheduler: promoting campaign %s (%s) to sending", campaign.id, campaign.name)
        campaign.status = "sending"
        campaign.save(update_fields=["status"])


def _tick():
    global _allowance
    from django.db import close_old_connections
    from .tasks import process_sending_campaigns

    # Este hilo vive fuera del ciclo request/response, así que Django nunca
    # detecta ni repone conexiones muertas (p.ej. tras un restart de postgres
    # por unattended-upgrades). Lo hacemos a mano en cada tick, igual que
    # Django hace automáticamente por request.
    close_old_connections()

    _promote_due_scheduled()

    rate = _get_rate_per_hour()
    # Acumula los correos que tocan en este tick según la tasa/hora.
    _allowance += rate * TICK_SECONDS / 3600.0
    budget = int(_allowance)
    if budget <= 0:
        return
    # Consumimos el presupuesto asignado (haya o no destinatarios), así el
    # promedio se mantiene en rate/h y el remanente fraccionario se conserva.
    _allowance -= budget
    sent = process_sending_campaigns(budget)
    if sent:
        log.info("Scheduler: sent %s message(s) this tick (rate=%s/h)", sent, rate)


def _loop():
    last_automation = 0.0
    while True:
        try:
            _tick()
        except Exception:
            log.exception("Scheduler tick crashed; will retry next interval")

        now = time.monotonic()
        if now - last_automation >= AUTOMATION_EVERY_SECONDS:
            last_automation = now
            try:
                from apps.automations.tasks import process_automation_queue
                process_automation_queue.delay()
            except Exception:
                log.exception("Failed to dispatch process_automation_queue")

        time.sleep(TICK_SECONDS)


def start():
    t = threading.Thread(target=_loop, daemon=True, name="mailerup-scheduler")
    t.start()
    log.info("[mailerup-scheduler] started (tick %ss, rate from Settings)", TICK_SECONDS)
    print(
        f"[mailerup-scheduler] iniciado (tick {TICK_SECONDS}s, ritmo configurable en Ajustes)",
        flush=True,
    )
