"""Informe de conversión de campañas: aperturas, clics, VENTAS atribuidas y resultado del A/B de asuntos.

Uso (root):
  cd /opt/mailerup/backend && sudo DJANGO_SETTINGS_MODULE=mailerup.settings.production \
      venv/bin/python manage.py shell < /opt/mailerup/scripts/informe_conversion.py

Atribución: una venta se asigna a la campaña cuyo enlace a un curso/kit hizo clic ese suscriptor en los
7 días previos al pago (último clic). Es una atribución de «último toque»: orientativa, no exacta.
"""
import collections, datetime, html as H, json, math, subprocess, zoneinfo
from django.db.models import Count
from apps.campaigns.models import Campaign, CampaignSend
from apps.analytics.models import EmailOpen, EmailClick
from apps.subscribers.models import Subscriber

MAD = zoneinfo.ZoneInfo("Europe/Madrid")
DIAS = 14  # ventana del informe por campañas
paid = json.loads(subprocess.run(["/opt/elrincondelhacker/venv/bin/python", "/opt/elrincondelhacker/scripts/exportar_pagos.py"],
                                 capture_output=True, text=True).stdout.strip().splitlines()[-1])
subs = {s.email.lower(): s.id for s in Subscriber.objects.all()}
sale_of = {}   # (campaña, suscriptor) -> €
for p in paid:
    sid = subs.get(p["email"])
    if not sid:
        continue
    t = datetime.datetime.fromtimestamp(p["ts"], tz=datetime.timezone.utc)
    ck = EmailClick.objects.filter(subscriber_id=sid, clicked_at__gte=t - datetime.timedelta(days=7), clicked_at__lte=t).order_by("-clicked_at")
    for c in ck:
        if "/curso/" in H.unescape(c.url or ""):
            sale_of[(str(c.campaign_id), str(sid))] = sale_of.get((str(c.campaign_id), str(sid)), 0) + p["eur"]
            break

since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=DIAS)
camps = list(Campaign.objects.filter(status="sent", sent_at__gte=since).order_by("scheduled_at"))
print(f"=== CAMPAÑAS ENVIADAS EN LOS ÚLTIMOS {DIAS} DÍAS ({len(camps)}) ===")
print(f"{'fecha':10} {'envíos':>6} {'apert%':>6} {'clic%':>6} {'ventas€':>8}  asunto")
for c in camps:
    n = CampaignSend.objects.filter(campaign=c).count() or 1
    o = EmailOpen.objects.filter(campaign=c).values("subscriber").distinct().count()
    k = EmailClick.objects.filter(campaign=c).values("subscriber").distinct().count()
    eur = sum(v for (cid, _), v in sale_of.items() if cid == str(c.id))
    d = (c.scheduled_at or c.sent_at).astimezone(MAD).strftime("%d/%m")
    print(f"{d:10} {n:6} {100*o/n:6.1f} {100*k/n:6.2f} {eur:8.0f}  {c.subject[:64]}")

# ---- A/B de asuntos (todas las campañas con A/B ya enviadas) ----
ab = list(Campaign.objects.filter(status="sent", ab_enabled=True))
print(f"\n=== A/B DE ASUNTOS ({len(ab)} campañas enviadas con A/B) ===")
if not ab:
    print("Todavía no hay campañas con A/B enviadas. Las 35 programadas empiezan a enviarse el 27/09.")
else:
    tot = {"A": collections.Counter(), "B": collections.Counter()}
    for c in ab:
        sends = {str(s.subscriber_id): s.ab_variant for s in CampaignSend.objects.filter(campaign=c)}
        opened = set(str(x) for x in EmailOpen.objects.filter(campaign=c).values_list("subscriber", flat=True).distinct())
        clicked = set(str(x) for x in EmailClick.objects.filter(campaign=c).values_list("subscriber", flat=True).distinct())
        for v in ("A", "B"):
            ids = {s for s, vv in sends.items() if vv == v}
            tot[v]["n"] += len(ids); tot[v]["open"] += len(ids & opened); tot[v]["click"] += len(ids & clicked)
            tot[v]["eur"] += sum(e for (cid, s), e in sale_of.items() if cid == str(c.id) and s in ids)
            tot[v]["ventas"] += sum(1 for (cid, s) in sale_of if cid == str(c.id) and s in ids)
    print(f"{'variante':9} {'envíos':>8} {'apert%':>7} {'clic%':>7} {'ventas':>6} {'€':>7}")
    for v in ("A", "B"):
        t = tot[v]; n = max(t["n"], 1)
        print(f"{v:9} {t['n']:8} {100*t['open']/n:7.2f} {100*t['click']/n:7.3f} {t['ventas']:6} {t['eur']:7.0f}")
    a, b = tot["A"], tot["B"]
    if a["n"] and b["n"]:
        p1, p2 = a["click"] / a["n"], b["click"] / b["n"]; pp = (a["click"] + b["click"]) / (a["n"] + b["n"])
        se = math.sqrt(pp * (1 - pp) * (1 / a["n"] + 1 / b["n"])) or 1
        z = (p2 - p1) / se
        print(f"\nDiferencia de clics B vs A: {100*(p2-p1):+.3f} pp (z={z:.2f}) -> " + ("SIGNIFICATIVA (95%)" if abs(z) > 1.96 else "aún no concluyente (necesita más envíos)"))
