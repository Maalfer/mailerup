"""Scoring automático de awareness_level a partir de aperturas/clics.

Corre dentro del mismo hilo del scheduler de campañas (ver
apps/campaigns/scheduler.py), como un tercer tick junto al de automatizaciones
y rebotes — no arranca ningún hilo/proceso propio.

Regla v1 (heurística simple y deliberadamente conservadora, pensada para
ajustarse con el tiempo — son constantes con nombre, no mágicas). El nivel
SOLO sube: nunca lo baja el scoring automático, para que un contacto no
"retroceda" solo por no abrir un correo. El nivel 5 ("listo para comprar") se
deja para asignación manual o para una futura fase con triggers por evento
(p.ej. clic en una página de precios), para no fingir una señal de compra que
el sistema no tiene hoy.
"""
import logging

from django.utils import timezone

log = logging.getLogger(__name__)

CLICKS_FOR_LEVEL_4 = 2
CLICKS_FOR_LEVEL_3 = 1
OPENS_FOR_LEVEL_3 = 3
OPENS_FOR_LEVEL_2 = 1


def _target_level(opens, clicks):
    if clicks >= CLICKS_FOR_LEVEL_4:
        return 4
    if clicks >= CLICKS_FOR_LEVEL_3 or opens >= OPENS_FOR_LEVEL_3:
        return 3
    if opens >= OPENS_FOR_LEVEL_2:
        return 2
    return 1


def run_scoring_tick():
    """Procesa solo suscriptores con eventos nuevos desde el último tick.
    Devuelve cuántos subieron de nivel."""
    from django.db.models import Count, Q
    from .models import ScoringCursor, Subscriber
    from apps.analytics.models import EmailOpen, EmailClick, AutomationEmailOpen, AutomationEmailClick

    cursor = ScoringCursor.get_solo()
    since = cursor.last_run_at
    now = timezone.now()

    touched_ids = set()
    open_filters = Q(opened_at__gt=since) if since else Q()
    click_filters = Q(clicked_at__gt=since) if since else Q()
    touched_ids.update(EmailOpen.objects.filter(open_filters).values_list("subscriber_id", flat=True))
    touched_ids.update(AutomationEmailOpen.objects.filter(open_filters).values_list("subscriber_id", flat=True))
    touched_ids.update(EmailClick.objects.filter(click_filters).values_list("subscriber_id", flat=True))
    touched_ids.update(AutomationEmailClick.objects.filter(click_filters).values_list("subscriber_id", flat=True))

    cursor.last_run_at = now
    cursor.save(update_fields=["last_run_at"])

    if not touched_ids:
        return 0

    subs = (
        Subscriber.objects.filter(id__in=touched_ids)
        .annotate(
            opens_total=Count("emailopen", distinct=True) + Count("automationemailopen", distinct=True),
            clicks_total=Count("emailclick", distinct=True) + Count("automationemailclick", distinct=True),
        )
    )
    raised = 0
    for sub in subs:
        target = _target_level(sub.opens_total, sub.clicks_total)
        if target > sub.awareness_level:
            sub.awareness_level = target
            sub.save(update_fields=["awareness_level"])
            raised += 1
    return raised
