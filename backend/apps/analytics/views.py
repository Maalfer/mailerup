import base64
import logging
from django.core import signing
from django.db.models import Count
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.utils.html import escape
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import permissions

logger = logging.getLogger(__name__)

from apps.campaigns.models import Campaign, CampaignSend
from apps.subscribers.models import Subscriber
from .models import (
    EmailOpen, EmailClick, EmailUnsubscribe, EmailBounce,
    AutomationEmailOpen, AutomationEmailClick,
)
from apps.automations.models import (
    Automation, AutomationEnrollment, AutomationSend,
)


UNSUBSCRIBE_SALT = "mailerup.unsubscribe.v1"
TRACK_SALT = "mailerup.track.v1"
AUTOTRACK_SALT = "mailerup.autotrack.v1"

def _shared_user(request):
    from apps.accounts.serializers import get_admin_user
    return get_admin_user() or request.user


# 1×1 transparent GIF
TRACKING_PIXEL = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)


def make_unsubscribe_token(subscriber_id, campaign_id=None):
    payload = {"s": str(subscriber_id)}
    if campaign_id:
        payload["c"] = str(campaign_id)
    return signing.dumps(payload, salt=UNSUBSCRIBE_SALT, compress=True)


def parse_unsubscribe_token(token, max_age_days=365):
    return signing.loads(token, salt=UNSUBSCRIBE_SALT, max_age=60 * 60 * 24 * max_age_days)


def make_track_token(campaign_id, subscriber_id):
    return signing.dumps({"c": str(campaign_id), "s": str(subscriber_id)}, salt=TRACK_SALT, compress=True)


def parse_track_token(token, max_age_days=365):
    return signing.loads(token, salt=TRACK_SALT, max_age=60 * 60 * 24 * max_age_days)


def make_auto_track_token(step_id, subscriber_id):
    return signing.dumps({"st": str(step_id), "s": str(subscriber_id)}, salt=AUTOTRACK_SALT, compress=True)


def parse_auto_track_token(token, max_age_days=365):
    return signing.loads(token, salt=AUTOTRACK_SALT, max_age=60 * 60 * 24 * max_age_days)


def _safe_redirect(url):
    """Redirige a URLs http(s) absolutas o rutas relativas propias (/path).
    Bloquea esquemas peligrosos (javascript:, data:…) y URLs scheme-relative
    (//evil.com) que podrían redirigir a otro dominio."""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
    except Exception:
        return redirect("/")
    if scheme in ("http", "https"):
        return redirect(url)
    # Ruta relativa propia: empieza por / pero NO por // (scheme-relative)
    if not scheme and url.startswith("/") and not url.startswith("//"):
        return redirect(url)
    return redirect("/")


class TrackOpenView(APIView):
    permission_classes = (permissions.AllowAny,)

    def get(self, request, token):
        try:
            data = parse_track_token(token)
            EmailOpen.objects.create(
                campaign_id=data["c"],
                subscriber_id=data["s"],
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
            )
        except signing.BadSignature:
            pass  # Token inválido/caducado — ignorar, devolver pixel igualmente
        except Exception:
            logger.exception("Unexpected error recording open for token %s", token)
        response = HttpResponse(TRACKING_PIXEL, content_type="image/gif")
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response


class TrackClickView(APIView):
    permission_classes = (permissions.AllowAny,)

    def get(self, request, token):
        url = request.GET.get("u", "/")
        try:
            data = parse_track_token(token)
        except signing.BadSignature:
            # Token inválido/caducado: NO honramos el `u` controlado por el
            # atacante (evita open redirect / phishing). Volvemos al inicio.
            return redirect("/")
        try:
            EmailClick.objects.create(
                campaign_id=data["c"],
                subscriber_id=data["s"],
                url=url[:200],
                ip_address=request.META.get("REMOTE_ADDR"),
            )
        except Exception:
            logger.exception("Unexpected error recording click for token %s", token)
        return _safe_redirect(url)


class TrackAutoOpenView(APIView):
    permission_classes = (permissions.AllowAny,)

    def get(self, request, token):
        try:
            data = parse_auto_track_token(token)
            AutomationEmailOpen.objects.create(
                step_id=data["st"],
                subscriber_id=data["s"],
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
            )
        except signing.BadSignature:
            pass  # Token inválido/caducado — ignorar, devolver pixel igualmente
        except Exception:
            logger.exception("Unexpected error recording auto open for token %s", token)
        response = HttpResponse(TRACKING_PIXEL, content_type="image/gif")
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response


class TrackAutoClickView(APIView):
    permission_classes = (permissions.AllowAny,)

    def get(self, request, token):
        url = request.GET.get("u", "/")
        try:
            data = parse_auto_track_token(token)
        except signing.BadSignature:
            # Token inválido/caducado: NO honramos el `u` controlado por el
            # atacante (evita open redirect / phishing). Volvemos al inicio.
            return redirect("/")
        try:
            AutomationEmailClick.objects.create(
                step_id=data["st"],
                subscriber_id=data["s"],
                url=url[:200],
                ip_address=request.META.get("REMOTE_ADDR"),
            )
        except Exception:
            logger.exception("Unexpected error recording auto click for token %s", token)
        return _safe_redirect(url)


UNSUB_PAGE = """<!doctype html>
<html lang="es"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
 body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#f8fafc;color:#0f172a;margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:1rem}}
 .card{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:2.5rem;max-width:480px;width:100%;box-shadow:0 1px 3px rgba(0,0,0,0.05);text-align:center}}
 h1{{margin:0 0 0.5rem 0;font-size:1.5rem;color:#0f172a}}
 p{{margin:0.5rem 0;color:#475569;line-height:1.5}}
 .email{{font-family:ui-monospace,monospace;background:#f1f5f9;padding:2px 6px;border-radius:4px}}
 .ico{{font-size:3rem;margin-bottom:0.5rem}}
 .muted{{color:#94a3b8;font-size:0.875rem;margin-top:1.5rem}}
</style></head><body>
<div class="card">{body}</div>
</body></html>"""


class UnsubscribeView(APIView):
    permission_classes = (permissions.AllowAny,)

    @staticmethod
    def _apply_unsubscribe(data):
        """Marca al suscriptor como dado de baja (idempotente). Devuelve
        (subscriber, already) o lanza Subscriber.DoesNotExist."""
        from django.utils import timezone
        subscriber = Subscriber.objects.get(pk=data["s"])
        already = subscriber.status == "unsubscribed"
        if not already:
            subscriber.status = "unsubscribed"
            subscriber.unsubscribed_at = timezone.now()
            subscriber.save(update_fields=["status", "unsubscribed_at"])
            campaign_id = data.get("c")
            if campaign_id:
                try:
                    campaign = Campaign.objects.get(pk=campaign_id)
                    EmailUnsubscribe.objects.create(campaign=campaign, subscriber=subscriber)
                except Campaign.DoesNotExist:
                    pass
            # La baja debe cortar también cualquier secuencia de automatización
            # en curso: sin esto la matrícula seguía "active" y el scheduler
            # continuaba enviando los pasos pendientes pese a la baja.
            AutomationEnrollment.objects.filter(
                subscriber=subscriber, status="active"
            ).update(status="cancelled")
        return subscriber, already

    def post(self, request, token):
        """Baja en un clic (RFC 8058). El cliente de correo (Gmail/Yahoo) hace
        POST con cuerpo `List-Unsubscribe=One-Click`; damos de baja sin pedir
        confirmación y respondemos 200 en texto plano (no se renderiza UI)."""
        try:
            data = parse_unsubscribe_token(token)
        except signing.BadSignature:
            return HttpResponse("invalid token", status=400, content_type="text/plain")
        try:
            self._apply_unsubscribe(data)
        except Subscriber.DoesNotExist:
            return HttpResponse("not found", status=404, content_type="text/plain")
        return HttpResponse("unsubscribed", status=200, content_type="text/plain")

    def get(self, request, token):
        try:
            data = parse_unsubscribe_token(token)
        except signing.BadSignature:
            body = '<div class="ico">⚠️</div><h1>Enlace inválido</h1><p>Este enlace de baja no es válido o ha caducado.</p>'
            return HttpResponse(UNSUB_PAGE.format(title="Enlace inválido", body=body), status=400)

        try:
            subscriber, already = self._apply_unsubscribe(data)
        except Subscriber.DoesNotExist:
            body = '<div class="ico">⚠️</div><h1>Suscriptor no encontrado</h1>'
            return HttpResponse(UNSUB_PAGE.format(title="No encontrado", body=body), status=404)

        title = "Ya estabas dado de baja" if already else "Baja confirmada"
        ico = "👋" if already else "✅"
        msg = (
            "Ya no estabas suscrito a esta newsletter."
            if already
            else "Has sido dado de baja. No volverás a recibir correos nuestros."
        )
        # subscriber.email se refleja en HTML: escapar (el alta pública solo valida
        # que contenga "@", así que un email con markup pasaría) para evitar XSS.
        body = f'<div class="ico">{ico}</div><h1>{title}</h1><p>{msg}</p><p><span class="email">{escape(subscriber.email)}</span></p><p class="muted">Puedes cerrar esta pestaña.</p>'
        return HttpResponse(UNSUB_PAGE.format(title=title, body=body))


def _campaign_stats(campaign):
    sends_qs = campaign.sends.all()
    sends = sends_qs.count()
    errored = sends_qs.filter(provider_message_id__startswith="error:").count()
    # Las tasas se calculan sobre lo REALMENTE entregado (sends - error de
    # envío inmediato). Un correo que nunca salió del servidor no puede
    # abrirse ni clicarse: incluirlo en el denominador infla artificialmente
    # a la baja el open/click rate.
    delivered = sends - errored
    unique_opens = EmailOpen.objects.filter(campaign=campaign).values("subscriber").distinct().count()
    unique_clicks = EmailClick.objects.filter(campaign=campaign).values("subscriber").distinct().count()
    unsubs = EmailUnsubscribe.objects.filter(campaign=campaign).count()
    bounces_qs = EmailBounce.objects.filter(campaign=campaign)
    hard_bounces = bounces_qs.filter(bounce_type="hard").count()
    soft_bounces = bounces_qs.filter(bounce_type="soft").count()
    return {
        "id": str(campaign.id),
        "name": campaign.name,
        "subject": campaign.subject,
        "status": campaign.status,
        "sent_at": campaign.sent_at,
        "sends": sends,
        "delivered": delivered,
        "errored": errored,
        "opens": unique_opens,
        "clicks": unique_clicks,
        "unsubscribes": unsubs,
        "hard_bounces": hard_bounces,
        "soft_bounces": soft_bounces,
        "not_opened": max(delivered - unique_opens, 0),
        "not_clicked": max(delivered - unique_clicks, 0),
        "open_rate": round(unique_opens / delivered * 100, 1) if delivered else 0,
        "click_rate": round(unique_clicks / delivered * 100, 1) if delivered else 0,
        "click_through_open_rate": round(unique_clicks / unique_opens * 100, 1) if unique_opens else 0,
        "unsubscribe_rate": round(unsubs / delivered * 100, 1) if delivered else 0,
        "bounce_rate": round((hard_bounces + soft_bounces) / delivered * 100, 1) if delivered else 0,
        "ab_enabled": campaign.ab_enabled,
    }


def _ab_variant_stats(campaign, variant):
    """Return send/open/click stats for a single A/B variant."""
    variant_sends = CampaignSend.objects.filter(campaign=campaign, ab_variant=variant)
    sends = variant_sends.count()
    # Solo los entregados (sin error de envío) cuentan como base de las tasas.
    send_ids = list(
        variant_sends.exclude(provider_message_id__startswith="error:")
        .values_list("subscriber_id", flat=True)
    )
    delivered = len(send_ids)
    opens = EmailOpen.objects.filter(
        campaign=campaign, subscriber_id__in=send_ids
    ).values("subscriber").distinct().count()
    clicks = EmailClick.objects.filter(
        campaign=campaign, subscriber_id__in=send_ids
    ).values("subscriber").distinct().count()
    return {
        "sends": sends,
        "delivered": delivered,
        "opens": opens,
        "clicks": clicks,
        "open_rate": round(opens / delivered * 100, 1) if delivered else 0,
        "click_rate": round(clicks / delivered * 100, 1) if delivered else 0,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def overview(request):
    user = _shared_user(request)
    campaigns_qs = Campaign.objects.filter(user=user)
    sent_qs = campaigns_qs.filter(status="sent")

    total_sends_qs = CampaignSend.objects.filter(campaign__user=user)
    total_sends = total_sends_qs.count()
    total_errored = total_sends_qs.filter(provider_message_id__startswith="error:").count()
    total_delivered = total_sends - total_errored
    unique_opens = EmailOpen.objects.filter(campaign__user=user).values("subscriber").distinct().count()
    unique_clicks = EmailClick.objects.filter(campaign__user=user).values("subscriber").distinct().count()
    unsubs = EmailUnsubscribe.objects.filter(campaign__user=user).count()
    total_bounces = EmailBounce.objects.filter(subscriber__list__user=user).count()

    total_subscribers = Subscriber.objects.filter(list__user=user, status="active").count()
    total_unsubscribed = Subscriber.objects.filter(list__user=user, status="unsubscribed").count()
    total_bounced = Subscriber.objects.filter(list__user=user, status="bounced").count()

    per_campaign = [_campaign_stats(c) for c in sent_qs.order_by("-sent_at")]

    return Response({
        "total_subscribers": total_subscribers,
        "total_unsubscribed": total_unsubscribed,
        "total_bounced": total_bounced,
        "total_campaigns": campaigns_qs.count(),
        "sent_campaigns": sent_qs.count(),
        "total_sends": total_sends,
        "total_delivered": total_delivered,
        "total_opens": unique_opens,
        "total_clicks": unique_clicks,
        "total_unsubscribes": unsubs,
        "total_bounces": total_bounces,
        "avg_open_rate": round(unique_opens / total_delivered * 100, 1) if total_delivered else 0,
        "avg_click_rate": round(unique_clicks / total_delivered * 100, 1) if total_delivered else 0,
        "campaigns": per_campaign,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def campaign_analytics(request, pk):
    try:
        campaign = Campaign.objects.get(pk=pk, user=_shared_user(request))
    except Campaign.DoesNotExist:
        return Response({"detail": "Campaña no encontrada"}, status=404)

    stats = _campaign_stats(campaign)
    opened_ids = set(
        EmailOpen.objects.filter(campaign=campaign).values_list("subscriber_id", flat=True).distinct()
    )
    clicked_ids = set(
        EmailClick.objects.filter(campaign=campaign).values_list("subscriber_id", flat=True).distinct()
    )

    recipients = []
    for send in campaign.sends.select_related("subscriber").order_by("-sent_at")[:500]:
        sub = send.subscriber
        recipients.append({
            "email": sub.email,
            "name": f"{sub.first_name} {sub.last_name}".strip(),
            "opened": sub.id in opened_ids,
            "clicked": sub.id in clicked_ids,
            "sent_at": send.sent_at,
        })

    top_links_qs = (
        EmailClick.objects.filter(campaign=campaign)
        .values("url")
        .annotate(clicks=Count("id"))
        .order_by("-clicks")[:10]
    )

    response_data = {
        **stats,
        "recipients": recipients,
        "top_links": list(top_links_qs),
    }

    if campaign.ab_enabled:
        a_stats = _ab_variant_stats(campaign, "A")
        b_stats = _ab_variant_stats(campaign, "B")
        a_stats["subject"] = campaign.subject
        b_stats["subject"] = campaign.subject_b
        response_data["ab_stats"] = {"A": a_stats, "B": b_stats}

    return Response(response_data)


# ---------------------------------------------------------------------------
# Analítica de AUTOMATIZACIONES
# ---------------------------------------------------------------------------

def _automation_step_stats(step, send_count):
    """Stats de un paso a partir de su nº de envíos y los registros de tracking."""
    opens = (
        AutomationEmailOpen.objects.filter(step=step)
        .values("subscriber").distinct().count()
    )
    clicks = (
        AutomationEmailClick.objects.filter(step=step)
        .values("subscriber").distinct().count()
    )
    return {
        "id": str(step.id),
        "order": step.order,
        "subject": step.subject,
        "sends": send_count,
        "opens": opens,
        "clicks": clicks,
        "open_rate": round(opens / send_count * 100, 1) if send_count else 0,
        "click_rate": round(clicks / send_count * 100, 1) if send_count else 0,
        "click_through_open_rate": round(clicks / opens * 100, 1) if opens else 0,
        "not_opened": max(send_count - opens, 0),
        "not_clicked": max(send_count - clicks, 0),
    }


def _automation_unsub_count(automation):
    """Bajas atribuidas a la automatización.

    No hay FK de EmailUnsubscribe a la automatización; contamos los suscriptores
    enrolados en la automatización cuyo estado actual es 'unsubscribed'. Es la
    mejor aproximación disponible sin alterar el modelo de bajas.
    """
    return (
        AutomationEnrollment.objects.filter(
            automation=automation, subscriber__status="unsubscribed"
        )
        .values("subscriber").distinct().count()
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def automations_overview(request):
    user = _shared_user(request)
    automations = (
        Automation.objects.filter(user=user)
        .prefetch_related("steps")
        .order_by("-created_at")
    )

    result = []
    for automation in automations:
        enrollments = AutomationEnrollment.objects.filter(automation=automation)
        enrolled = enrollments.count()
        active = enrollments.filter(status="active").count()
        completed = enrollments.filter(status="completed").count()

        step_ids = list(automation.steps.values_list("id", flat=True))
        sends = AutomationSend.objects.filter(step_id__in=step_ids).count()
        opens = (
            AutomationEmailOpen.objects.filter(step_id__in=step_ids)
            .values("subscriber", "step").distinct().count()
        )
        clicks = (
            AutomationEmailClick.objects.filter(step_id__in=step_ids)
            .values("subscriber", "step").distinct().count()
        )
        unsubs = _automation_unsub_count(automation)

        result.append({
            "id": str(automation.id),
            "name": automation.name,
            "is_active": automation.is_active,
            "steps_count": len(step_ids),
            "enrolled": enrolled,
            "active": active,
            "completed": completed,
            "sends": sends,
            "opens": opens,
            "clicks": clicks,
            "unsubscribes": unsubs,
            "open_rate": round(opens / sends * 100, 1) if sends else 0,
            "click_rate": round(clicks / sends * 100, 1) if sends else 0,
            "unsubscribe_rate": round(unsubs / enrolled * 100, 1) if enrolled else 0,
        })

    total_sends = sum(a["sends"] for a in result)
    total_opens = sum(a["opens"] for a in result)
    total_clicks = sum(a["clicks"] for a in result)

    return Response({
        "total_automations": len(result),
        "active_automations": sum(1 for a in result if a["is_active"]),
        "total_sends": total_sends,
        "total_opens": total_opens,
        "total_clicks": total_clicks,
        "avg_open_rate": round(total_opens / total_sends * 100, 1) if total_sends else 0,
        "avg_click_rate": round(total_clicks / total_sends * 100, 1) if total_sends else 0,
        "automations": result,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def automation_analytics(request, pk):
    try:
        automation = Automation.objects.get(pk=pk, user=_shared_user(request))
    except Automation.DoesNotExist:
        return Response({"detail": "Automatización no encontrada"}, status=404)

    enrollments = AutomationEnrollment.objects.filter(automation=automation)
    enrolled = enrollments.count()
    active = enrollments.filter(status="active").count()
    completed = enrollments.filter(status="completed").count()

    steps = list(automation.steps.order_by("order"))
    # nº de envíos por paso en una sola consulta
    send_counts = {}
    for row in (
        AutomationSend.objects.filter(step__automation=automation)
        .values("step").annotate(n=Count("id"))
    ):
        send_counts[row["step"]] = row["n"]

    per_step = [
        _automation_step_stats(step, send_counts.get(step.id, 0)) for step in steps
    ]

    total_sends = sum(s["sends"] for s in per_step)
    total_opens = sum(s["opens"] for s in per_step)
    total_clicks = sum(s["clicks"] for s in per_step)
    unsubs = _automation_unsub_count(automation)

    return Response({
        "id": str(automation.id),
        "name": automation.name,
        "is_active": automation.is_active,
        "enrolled": enrolled,
        "active": active,
        "completed": completed,
        "sends": total_sends,
        "opens": total_opens,
        "clicks": total_clicks,
        "unsubscribes": unsubs,
        "open_rate": round(total_opens / total_sends * 100, 1) if total_sends else 0,
        "click_rate": round(total_clicks / total_sends * 100, 1) if total_sends else 0,
        "unsubscribe_rate": round(unsubs / enrolled * 100, 1) if enrolled else 0,
        "steps": per_step,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def subscriptions_timeseries(request):
    """Serie temporal de ALTAS y BAJAS de la lista del usuario, agrupada por
    día / semana / mes (?period=day|week|month). Para ver cuánta gente entra y
    sale de la newsletter a lo largo del tiempo."""
    from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
    from apps.subscribers.models import SubscriberList, Subscriber

    period = request.GET.get("period", "day")
    trunc = {"day": TruncDay, "week": TruncWeek, "month": TruncMonth}.get(period, TruncDay)

    lst = SubscriberList.objects.filter(user=_shared_user(request)).order_by("created_at").first()
    if not lst:
        return Response({"period": period, "buckets": [], "total_altas": 0, "total_bajas": 0})

    import datetime
    # Fechas excluidas de la serie temporal (p.ej. días de migración masiva)
    EXCLUDED_DATES = {datetime.date(2026, 5, 30)}

    subs = Subscriber.objects.filter(list=lst)

    def _series(qs, field):
        rows = (
            qs.annotate(b=trunc(field)).values("b")
            .annotate(n=Count("id")).order_by("b")
        )
        result = {}
        for r in rows:
            if r["b"] is None:
                continue
            d = r["b"].date() if hasattr(r["b"], "date") else r["b"]
            if d not in EXCLUDED_DATES:
                result[r["b"]] = r["n"]
        return result

    altas = _series(subs, "subscribed_at")
    bajas = _series(subs.filter(unsubscribed_at__isnull=False), "unsubscribed_at")

    keys = sorted(set(altas) | set(bajas))
    buckets = [{
        "date": (k.date().isoformat() if hasattr(k, "date") else str(k)),
        "altas": altas.get(k, 0),
        "bajas": bajas.get(k, 0),
    } for k in keys]

    return Response({
        "period": period,
        "buckets": buckets,
        "total_altas": sum(altas.values()),
        "total_bajas": sum(bajas.values()),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def deliverability(request):
    """Entregabilidad: % de éxito/error de los envíos, motivos de error y
    progreso de las campañas en curso (enviados/pendientes, ritmo y ETA)."""
    from collections import Counter
    from apps.campaigns.models import Campaign, CampaignSend
    from apps.campaigns.tasks import _pending_subscribers

    user = _shared_user(request)
    sends = CampaignSend.objects.filter(campaign__user=user)
    total = sends.count()
    errored = sends.filter(provider_message_id__startswith="error:").count()
    ok = total - errored

    reasons = Counter()
    for pid in sends.filter(provider_message_id__startswith="error:").values_list("provider_message_id", flat=True):
        r = (pid[len("error:"):].strip() or "(desconocido)")[:140]
        reasons[r] += 1
    top_errors = [
        {"reason": r, "count": n, "rate": round(n / errored * 100, 1) if errored else 0}
        for r, n in reasons.most_common(15)
    ]

    # Rebotes REALES (NDR post-entrega), a diferencia de `errored` arriba que
    # solo son fallos síncronos del propio envío. Requieren el pipeline de
    # ingesta del buzón de rebotes (ver bounce_processing.py); si no está
    # configurado, estos contadores se quedan a 0 sin romper nada.
    bounces = EmailBounce.objects.filter(subscriber__list__user=user)
    hard_bounces = bounces.filter(bounce_type="hard").count()
    soft_bounces = bounces.filter(bounce_type="soft").count()
    total_bounces = hard_bounces + soft_bounces
    bounce_reasons = Counter()
    for reason in bounces.values_list("reason", flat=True):
        bounce_reasons[(reason.strip() or "(desconocido)")[:140]] += 1
    top_bounce_reasons = [
        {"reason": r, "count": n, "rate": round(n / total_bounces * 100, 1) if total_bounces else 0}
        for r, n in bounce_reasons.most_common(15)
    ]

    sending = []
    total_pending = 0
    for c in Campaign.objects.filter(user=user, status__in=("sending", "paused")).order_by("created_at"):
        sent = CampaignSend.objects.filter(campaign=c).count()
        pending = _pending_subscribers(c).count()
        tot = sent + pending
        if c.status == "sending":
            total_pending += pending  # solo las activas cuentan para el ETA
        sending.append({
            "id": str(c.id), "name": c.name, "subject": c.subject, "status": c.status,
            "sent": sent, "pending": pending, "total": tot,
            "progress": round(sent / tot * 100, 1) if tot else 0,
        })

    # Correos ya enviados (para poder consultar sus destinatarios desde aquí).
    sent_campaigns = [
        {
            "id": str(c.id), "name": c.name, "subject": c.subject,
            "sent_at": c.sent_at, "sends": c.n,
        }
        for c in (
            Campaign.objects.filter(user=user, status="sent")
            .annotate(n=Count("sends"))
            .order_by("-sent_at")[:50]
        )
    ]

    rate = max(1, int(getattr(user, "send_rate_per_hour", 300) or 300))
    return Response({
        "total_sends": total,
        "ok": ok,
        "errored": errored,
        "success_rate": round(ok / total * 100, 1) if total else 0,
        "error_rate": round(errored / total * 100, 1) if total else 0,
        "top_errors": top_errors,
        "hard_bounces": hard_bounces,
        "soft_bounces": soft_bounces,
        "total_bounces": total_bounces,
        "bounce_rate": round(total_bounces / ok * 100, 1) if ok else 0,
        "top_bounce_reasons": top_bounce_reasons,
        "sending": sending,
        "sent": sent_campaigns,
        "rate_per_hour": rate,
        "total_pending": total_pending,
        "eta_hours": round(total_pending / rate, 1) if total_pending else 0,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def retry_failed_sends(request):
    """Re-encola los envíos que fallaron: borra sus CampaignSend con error (vuelven
    a quedar 'pendientes') y reactiva esas campañas a 'sending' para que el
    scheduler los reintente al ritmo configurado, sin reenviar a los que sí
    llegaron."""
    from apps.campaigns.models import Campaign, CampaignSend

    failed = CampaignSend.objects.filter(
        campaign__user=_shared_user(request), provider_message_id__startswith="error:"
    )
    campaign_ids = list(failed.values_list("campaign_id", flat=True).distinct())
    count = failed.count()
    failed.delete()
    reactivated = (
        Campaign.objects.filter(id__in=campaign_ids)
        .exclude(status="sending")
        .update(status="sending")
    )
    return Response({"requeued": count, "campaigns": len(campaign_ids), "reactivated": reactivated})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def deliverability_recipients(request, pk):
    """Destinatarios de una campaña para la página de Entregabilidad.

    Permite ver quién ya ha recibido el correo (con estado entregado/error) y,
    si la campaña se está enviando, quién está todavía pendiente. Soporta
    búsqueda por email o nombre (``?q=``) y filtro por categoría
    (``?filter=received|pending|error``). Las listas se limitan a ``LIMIT``
    filas para no devolver payloads enormes; los contadores son siempre el total
    real."""
    from django.db.models import Q
    from apps.campaigns.models import Campaign, CampaignSend
    from apps.campaigns.tasks import _pending_subscribers

    try:
        campaign = Campaign.objects.get(pk=pk, user=_shared_user(request))
    except Campaign.DoesNotExist:
        return Response({"detail": "Campaña no encontrada"}, status=404)

    LIMIT = 500
    q = (request.GET.get("q") or "").strip()
    filt = request.GET.get("filter", "received")
    if filt not in ("received", "pending", "error"):
        filt = "received"

    sends = CampaignSend.objects.filter(campaign=campaign)
    received_count = sends.count()
    error_count = sends.filter(provider_message_id__startswith="error:").count()
    pending_qs = _pending_subscribers(campaign)
    pending_count = pending_qs.count()

    def _search(qs, fields):
        if not q:
            return qs
        cond = Q()
        for f in fields:
            cond |= Q(**{f"{f}__icontains": q})
        return qs.filter(cond)

    results = []
    if filt == "pending":
        rows = _search(pending_qs, ["email", "first_name", "last_name"])[:LIMIT]
        for sub in rows:
            results.append({
                "email": sub.email,
                "name": f"{sub.first_name} {sub.last_name}".strip(),
                "status": "pending",
                "error_reason": "",
                "sent_at": None,
            })
    else:
        rows = sends.select_related("subscriber").order_by("-sent_at")
        if filt == "error":
            rows = rows.filter(provider_message_id__startswith="error:")
        rows = _search(
            rows, ["subscriber__email", "subscriber__first_name", "subscriber__last_name"]
        )[:LIMIT]
        for send in rows:
            sub = send.subscriber
            is_err = send.provider_message_id.startswith("error:")
            results.append({
                "email": sub.email,
                "name": f"{sub.first_name} {sub.last_name}".strip(),
                "status": "error" if is_err else "ok",
                "error_reason": (
                    (send.provider_message_id[len("error:"):].strip() or "(desconocido)")[:200]
                    if is_err else ""
                ),
                "sent_at": send.sent_at,
            })

    return Response({
        "campaign": {
            "id": str(campaign.id), "name": campaign.name,
            "subject": campaign.subject, "status": campaign.status,
        },
        "counts": {
            "received": received_count, "error": error_count, "pending": pending_count,
        },
        "filter": filt,
        "q": q,
        "results": results,
        "truncated": len(results) >= LIMIT,
        "limit": LIMIT,
    })
