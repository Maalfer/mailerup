"""Sincroniza las compras de la tienda (tabla payments, MariaDB) con analytics_purchase (MailerUp) y las
atribuye a su suscriptor: por `mu` (ID exacto que viaja en el enlace del correo) o, si falta, por email.
Idempotente. Se ejecuta cada 10 min vía systemd (mailerup-sync-compras.timer -> .service).
Manual: cd /opt/mailerup/backend && DJANGO_SETTINGS_MODULE=mailerup.settings.production venv/bin/python manage.py shell < ../scripts/sync_compras.py
"""
import datetime, json, subprocess, uuid
from apps.analytics.models import Purchase
from apps.subscribers.models import Subscriber

raw = subprocess.run(["/opt/elrincondelhacker/venv/bin/python", "/opt/elrincondelhacker/scripts/exportar_payments_db.py"],
                     capture_output=True, text=True)
rows = json.loads(raw.stdout.strip().splitlines()[-1])
by_email = {}
for s in Subscriber.objects.only("id", "email", "subscribed_at").order_by("subscribed_at"):
    by_email.setdefault(s.email.lower(), s.id)   # si el email está en varios grupos, el alta más antigua
n_new = n_upd = n_mu = n_email = 0
for r in rows:
    sub_id, how = None, ""
    try:
        cand = uuid.UUID(r["mailerup_sid"]) if r.get("mailerup_sid") not in (None, "", "None") else None
        if cand and Subscriber.objects.filter(pk=cand).exists():
            sub_id, how = cand, "mu"
    except ValueError:
        pass
    if not sub_id and by_email.get(r["email"]):
        sub_id, how = by_email[r["email"]], "email"
    n_mu += how == "mu"; n_email += how == "email"
    vals = dict(email=r["email"], subscriber_id=sub_id, item_type=r["item_type"] or "", item_title=(r["item_title"] or "")[:255],
                amount_cents=int(r["amount_cents"] or 0), refunded_cents=int(r["refunded_cents"] or 0), origin=r["origin"] or "",
                paid_at=datetime.datetime.fromtimestamp(float(r["ts"]), tz=datetime.timezone.utc),
                utm_source=r["utm_source"] or "", utm_medium=r["utm_medium"] or "", utm_campaign=r["utm_campaign"] or "",
                utm_content=r["utm_content"] or "", mailerup_sid=r["mailerup_sid"] or "", attribution=how)
    _, created = Purchase.objects.update_or_create(stripe_session_id=r["sid"], defaults=vals)
    n_new += created; n_upd += (not created)
print(f"sync_compras: {len(rows)} pagos | nuevos={n_new} actualizados={n_upd} | atribuidos por mu={n_mu} por email={n_email}")

# Marca como cliente a todo suscriptor (en cualquier grupo) cuyo email tenga alguna compra no reembolsada
# entera; es lo que usan "Excluir compradores" y el segmento "Cliente" de las campañas.
from django.db.models import F, Max
from django.db.models.functions import Lower
paid = {}
for p in Purchase.objects.filter(amount_cents__gt=F("refunded_cents")).values("email").annotate(last=Max("paid_at")):
    paid[p["email"].lower()] = p["last"]
n_cli = 0
for s in Subscriber.objects.annotate(le=Lower("email")).filter(le__in=list(paid)).only("id", "email", "lifecycle_stage", "last_purchase_at"):
    last = paid[s.email.lower()]
    if s.lifecycle_stage != "cliente" or s.last_purchase_at != last:
        Subscriber.objects.filter(pk=s.pk).update(lifecycle_stage="cliente", last_purchase_at=last)
        n_cli += 1
print(f"sync_compras: clientes marcados/actualizados={n_cli}")

# Además: cliente = tener algún curso o pack asignado en la academia (matrículas), aunque no haya pago en `payments`
# (alumnos importados/previos a mayo de 2026, accesos manuales, cursos gratuitos).
raw = subprocess.run(["/opt/elrincondelhacker/venv/bin/python", "/opt/elrincondelhacker/scripts/exportar_alumnos_db.py"],
                     capture_output=True, text=True)
alumnos = json.loads(raw.stdout.strip().splitlines()[-1])
n_alu = 0
for s in Subscriber.objects.annotate(le=Lower("email")).filter(le__in=list(alumnos)).only("id", "email", "lifecycle_stage", "last_purchase_at"):
    if s.lifecycle_stage != "cliente":
        Subscriber.objects.filter(pk=s.pk).update(
            lifecycle_stage="cliente",
            last_purchase_at=s.last_purchase_at or datetime.datetime.fromtimestamp(alumnos[s.email.lower()], tz=datetime.timezone.utc))
        n_alu += 1
print(f"sync_compras: clientes marcados por curso asignado={n_alu} (alumnos en academia={len(alumnos)})")
