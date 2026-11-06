"""Vistas SQL de trazabilidad de leads (lead_events, lead_funnel, step_funnel, funnel_by_source).
Solo lectura: se pueden recrear en cualquier momento. Ver docs/TRAZABILIDAD.md."""
from django.db import migrations

FORWARD = r"""
CREATE OR REPLACE FUNCTION lead_click_kind(u text) RETURNS text LANGUAGE sql IMMUTABLE AS $f$
  SELECT CASE
    WHEN u ~* '/curso/|pagina-de-ventas' THEN 'curso'
    WHEN u ~* 'drive\.google|/recurso' THEN 'recurso'
    WHEN u ~* 'youtu' THEN 'youtube'
    WHEN u ~* 'skool\.com' THEN 'comunidad'
    WHEN u ~* 'elrincondelhacker\.es' THEN 'web'
    ELSE 'otro' END
$f$;

-- Línea de tiempo unificada: una fila por evento de cada lead.
CREATE OR REPLACE VIEW lead_events AS
SELECT a.created_at AS event_at, a.subscriber_id, a.email::text AS email, 'form_submitted'::text AS event,
       coalesce(nullif(a.source,''),'desconocido')::text AS source, NULL::text AS automation, NULL::int AS step_order, a.outcome::text AS detail
  FROM analytics_signupattempt a
UNION ALL
SELECT s.subscribed_at, s.id, s.email::text, 'confirmed', coalesce(nullif(s.source,''),'desconocido'), NULL, NULL,
       s.attribution_method::text
  FROM subscribers_subscriber s
UNION ALL
SELECT e.enrolled_at, e.subscriber_id, s.email::text, 'enrolled', coalesce(nullif(s.source,''),'desconocido'), au.name::text, NULL, e.status::text
  FROM automations_automationenrollment e
  JOIN automations_automation au ON au.id = e.automation_id
  JOIN subscribers_subscriber s ON s.id = e.subscriber_id
UNION ALL
SELECT sd.sent_at, e.subscriber_id, s.email::text, 'email_sent', coalesce(nullif(s.source,''),'desconocido'), au.name::text, st."order"::int, left(st.subject,80)
  FROM automations_automationsend sd
  JOIN automations_automationenrollment e ON e.id = sd.enrollment_id
  JOIN automations_automationstep st ON st.id = sd.step_id
  JOIN automations_automation au ON au.id = st.automation_id
  JOIN subscribers_subscriber s ON s.id = e.subscriber_id
UNION ALL
SELECT o.opened_at, o.subscriber_id, s.email::text, 'email_open', coalesce(nullif(s.source,''),'desconocido'), au.name::text, st."order"::int, left(o.user_agent,80)
  FROM analytics_automationemailopen o
  JOIN automations_automationstep st ON st.id = o.step_id
  JOIN automations_automation au ON au.id = st.automation_id
  JOIN subscribers_subscriber s ON s.id = o.subscriber_id
UNION ALL
SELECT c.clicked_at, c.subscriber_id, s.email::text, 'email_click', coalesce(nullif(s.source,''),'desconocido'), au.name::text, st."order"::int,
       lead_click_kind(c.url) || ' ' || c.url
  FROM analytics_automationemailclick c
  JOIN automations_automationstep st ON st.id = c.step_id
  JOIN automations_automation au ON au.id = st.automation_id
  JOIN subscribers_subscriber s ON s.id = c.subscriber_id
UNION ALL
SELECT u.unsubscribed_at, u.subscriber_id, s.email::text, 'unsubscribed', coalesce(nullif(s.source,''),'desconocido'), NULL, NULL, left(u.reason,80)
  FROM analytics_emailunsubscribe u JOIN subscribers_subscriber s ON s.id = u.subscriber_id
UNION ALL
SELECT b.bounced_at, b.subscriber_id, s.email::text, 'bounced', coalesce(nullif(s.source,''),'desconocido'), NULL, NULL, b.bounce_type::text
  FROM analytics_emailbounce b JOIN subscribers_subscriber s ON s.id = b.subscriber_id
UNION ALL
SELECT p.paid_at, p.subscriber_id, p.email::text, 'purchase', coalesce(nullif(s.source,''),'desconocido'), NULL, NULL,
       p.item_title || ' | ' || round((p.amount_cents - p.refunded_cents)/100.0, 2) || ' EUR | atribución=' || coalesce(nullif(p.attribution,''),'ninguna')
  FROM analytics_purchase p LEFT JOIN subscribers_subscriber s ON s.id = p.subscriber_id;

-- Una fila por lead con todo su recorrido resumido.
CREATE OR REPLACE VIEW lead_funnel AS
SELECT s.id AS subscriber_id, s.email::text AS email, s.subscribed_at,
       coalesce(nullif(s.source,''),'desconocido') AS source, s.utm_source, s.utm_medium, s.utm_campaign, s.utm_content,
       s.manychat_sid, s.attribution_method, s.status, s.lifecycle_stage,
       coalesce(snd.steps_sent,0) AS steps_sent, snd.last_step_sent,
       coalesce(op.opened_steps,0) AS opened_steps, op.last_step_opened, op.first_open_at,
       coalesce(ck.clicked_steps,0) AS clicked_steps, ck.last_step_clicked, ck.first_click_at,
       coalesce(ck.clicked_course,false) AS clicked_course, coalesce(ck.clicked_resource,false) AS clicked_resource,
       un.unsubscribed_at,
       coalesce(pu.purchases,0) AS purchases, coalesce(pu.revenue_eur,0) AS revenue_eur,
       pu.first_purchase_at, (pu.first_purchase_at - s.subscribed_at) AS time_to_purchase
  FROM subscribers_subscriber s
  LEFT JOIN (SELECT e.subscriber_id, count(*) AS steps_sent, max(st."order") AS last_step_sent
               FROM automations_automationsend sd
               JOIN automations_automationenrollment e ON e.id = sd.enrollment_id
               JOIN automations_automationstep st ON st.id = sd.step_id GROUP BY 1) snd ON snd.subscriber_id = s.id
  LEFT JOIN (SELECT o.subscriber_id, count(DISTINCT o.step_id) AS opened_steps, max(st."order") AS last_step_opened, min(o.opened_at) AS first_open_at
               FROM analytics_automationemailopen o JOIN automations_automationstep st ON st.id = o.step_id GROUP BY 1) op ON op.subscriber_id = s.id
  LEFT JOIN (SELECT c.subscriber_id, count(DISTINCT c.step_id) AS clicked_steps, max(st."order") AS last_step_clicked, min(c.clicked_at) AS first_click_at,
                    bool_or(lead_click_kind(c.url) = 'curso') AS clicked_course, bool_or(lead_click_kind(c.url) IN ('recurso','youtube')) AS clicked_resource
               FROM analytics_automationemailclick c JOIN automations_automationstep st ON st.id = c.step_id GROUP BY 1) ck ON ck.subscriber_id = s.id
  LEFT JOIN (SELECT subscriber_id, min(unsubscribed_at) AS unsubscribed_at FROM analytics_emailunsubscribe GROUP BY 1) un ON un.subscriber_id = s.id
  LEFT JOIN (SELECT subscriber_id, count(*) AS purchases, sum((amount_cents - refunded_cents)/100.0) AS revenue_eur, min(paid_at) AS first_purchase_at
               FROM analytics_purchase WHERE subscriber_id IS NOT NULL GROUP BY 1) pu ON pu.subscriber_id = s.id;

-- Embudo por paso de la secuencia (y por origen): dónde se cae el interés.
CREATE OR REPLACE VIEW step_funnel AS
SELECT au.name AS automation, st."order" AS step_order, left(st.subject,70) AS subject,
       coalesce(nullif(s.source,''),'desconocido') AS source,
       count(DISTINCT e.subscriber_id) AS sent,
       count(DISTINCT o.subscriber_id) AS opened,
       count(DISTINCT c.subscriber_id) AS clicked,
       count(DISTINCT c.subscriber_id) FILTER (WHERE lead_click_kind(c.url) = 'curso') AS clicked_course,
       count(DISTINCT u.subscriber_id) FILTER (WHERE u.unsubscribed_at >= sd.sent_at AND u.unsubscribed_at < sd.sent_at + interval '48 hours') AS unsub_48h
  FROM automations_automationsend sd
  JOIN automations_automationenrollment e ON e.id = sd.enrollment_id
  JOIN automations_automationstep st ON st.id = sd.step_id
  JOIN automations_automation au ON au.id = st.automation_id
  JOIN subscribers_subscriber s ON s.id = e.subscriber_id
  LEFT JOIN analytics_automationemailopen o ON o.step_id = sd.step_id AND o.subscriber_id = e.subscriber_id
  LEFT JOIN analytics_automationemailclick c ON c.step_id = sd.step_id AND c.subscriber_id = e.subscriber_id
  LEFT JOIN analytics_emailunsubscribe u ON u.subscriber_id = e.subscriber_id
 GROUP BY 1,2,3,4;

-- Embudo completo por origen: visitas -> formulario -> alta -> recibe -> abre -> clic -> clic en curso -> compra.
CREATE OR REPLACE VIEW funnel_by_source AS
WITH v AS (SELECT coalesce(nullif(source,''),'desconocido') AS source, count(DISTINCT visitor_id) AS visitors FROM analytics_landingvisit GROUP BY 1),
     a AS (SELECT coalesce(nullif(source,''),'desconocido') AS source, count(DISTINCT lower(email)) AS form_submitters FROM analytics_signupattempt GROUP BY 1),
     f AS (SELECT source, count(*) AS confirmed,
                  count(*) FILTER (WHERE steps_sent > 0) AS received_email,
                  count(*) FILTER (WHERE opened_steps > 0) AS opened_any,
                  count(*) FILTER (WHERE clicked_steps > 0) AS clicked_any,
                  count(*) FILTER (WHERE clicked_course) AS clicked_course,
                  count(*) FILTER (WHERE unsubscribed_at IS NOT NULL) AS unsubscribed,
                  count(*) FILTER (WHERE purchases > 0) AS buyers,
                  coalesce(sum(revenue_eur),0)::numeric(10,2) AS revenue_eur
             FROM lead_funnel GROUP BY 1)
SELECT coalesce(f.source, a.source, v.source) AS source, v.visitors, a.form_submitters, f.confirmed, f.received_email, f.opened_any,
       f.clicked_any, f.clicked_course, f.unsubscribed, f.buyers, f.revenue_eur
  FROM f FULL OUTER JOIN a ON a.source = f.source FULL OUTER JOIN v ON v.source = coalesce(f.source, a.source);

"""

REVERSE = """
DROP VIEW IF EXISTS funnel_by_source;
DROP VIEW IF EXISTS step_funnel;
DROP VIEW IF EXISTS lead_funnel;
DROP VIEW IF EXISTS lead_events;
DROP FUNCTION IF EXISTS lead_click_kind(text);
"""


class Migration(migrations.Migration):
    dependencies = [("analytics", "0004_landingvisit_automationemailclick_user_agent_and_more")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
