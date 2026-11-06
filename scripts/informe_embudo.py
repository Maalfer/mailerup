"""Informe de embudo y trazabilidad de leads (lee las vistas SQL de la migración analytics.0005).
Uso: cd /opt/mailerup/backend && sudo DJANGO_SETTINGS_MODULE=mailerup.settings.production venv/bin/python manage.py shell < ../scripts/informe_embudo.py
Ajusta DESDE para acotar por fecha de alta. Ver /opt/mailerup/docs/TRAZABILIDAD.md"""
from django.db import connection
DESDE = "2000-01-01"

def q(title, sql, params=None):
    with connection.cursor() as c:
        c.execute(sql, params or [])
        cols = [d[0] for d in c.description]; rows = c.fetchall()
    print(f"\n=== {title} ===")
    w = [max(len(str(x)) for x in [cols[i]] + [r[i] for r in rows]) for i in range(len(cols))]
    print("  ".join(str(cols[i]).ljust(w[i]) for i in range(len(cols))))
    for r in rows:
        print("  ".join(str("" if r[i] is None else r[i]).ljust(w[i]) for i in range(len(cols))))

q("1. EMBUDO POR ORIGEN (visitas -> formulario -> alta -> abre -> clic -> clic en curso -> compra)",
  """SELECT source, confirmed AS altas, received_email AS reciben, opened_any AS abren, clicked_any AS clic,
            clicked_course AS clic_curso, unsubscribed AS bajas, buyers AS compran, revenue_eur AS eur,
            round(100.0*buyers/nullif(confirmed,0),2) AS pct_compra
       FROM (SELECT source, count(*) confirmed, count(*) FILTER (WHERE steps_sent>0) received_email,
                    count(*) FILTER (WHERE opened_steps>0) opened_any, count(*) FILTER (WHERE clicked_steps>0) clicked_any,
                    count(*) FILTER (WHERE clicked_course) clicked_course, count(*) FILTER (WHERE unsubscribed_at IS NOT NULL) unsubscribed,
                    count(*) FILTER (WHERE purchases>0) buyers, coalesce(sum(revenue_eur),0)::numeric(10,2) revenue_eur
               FROM lead_funnel WHERE subscribed_at >= %s GROUP BY 1) t ORDER BY altas DESC""", [DESDE])

q("2. PARTE ALTA: visitas de captación -> formularios enviados -> confirmados (por origen)",
  """WITH v AS (SELECT coalesce(nullif(source,''),'desconocido') AS source, count(DISTINCT visitor_id) AS visitantes
                FROM analytics_landingvisit WHERE created_at >= %s GROUP BY 1),
          a AS (SELECT coalesce(nullif(source,''),'desconocido') AS source, count(*) AS envios_form,
                       count(*) FILTER (WHERE outcome='confirmed') AS confirmados
                FROM analytics_signupattempt WHERE created_at >= %s GROUP BY 1)
     SELECT coalesce(v.source, a.source) AS source, v.visitantes, a.envios_form, a.confirmados,
            round(100.0*a.envios_form/nullif(v.visitantes,0),1) AS pct_visita_a_form,
            round(100.0*a.confirmados/nullif(a.envios_form,0),1) AS pct_form_a_confirmado
       FROM v FULL OUTER JOIN a ON a.source = v.source ORDER BY 2 DESC NULLS LAST""", [DESDE, DESDE])

q("3. PASO A PASO de la secuencia-academia: dónde se pierde el interés (todos los orígenes)",
  """SELECT step_order AS paso, subject AS asunto, sum(sent) AS enviados, sum(opened) AS abren, sum(clicked) AS clic,
            sum(clicked_course) AS clic_curso, sum(unsub_48h) AS bajas_48h,
            round(100.0*sum(opened)/nullif(sum(sent),0),1) AS pct_apertura, round(100.0*sum(clicked)/nullif(sum(sent),0),1) AS pct_clic
       FROM step_funnel WHERE automation='secuencia-academia' GROUP BY 1,2 ORDER BY 1""")

q("4. PASO A PASO solo de leads ManyChat",
  """SELECT step_order AS paso, sent AS enviados, opened AS abren, clicked AS clic, clicked_course AS clic_curso, unsub_48h AS bajas_48h
       FROM step_funnel WHERE automation='secuencia-academia' AND source='manychat' ORDER BY 1""")

q("5. ÚLTIMO PASO QUE ABRE cada lead (dónde dejan de leer)",
  """SELECT coalesce(last_step_opened::text,'nunca abre') AS ultimo_paso_abierto, count(*) AS leads
       FROM lead_funnel WHERE steps_sent>0 AND subscribed_at>=%s GROUP BY 1 ORDER BY 1""", [DESDE])

q("6. COHORTES SEMANALES: altas, abren, clic en curso, compran",
  """SELECT date_trunc('week', subscribed_at)::date AS semana, source, count(*) AS altas, count(*) FILTER (WHERE opened_steps>0) AS abren,
            count(*) FILTER (WHERE clicked_course) AS clic_curso, count(*) FILTER (WHERE purchases>0) AS compran, coalesce(sum(revenue_eur),0)::numeric(10,2) AS eur
       FROM lead_funnel WHERE subscribed_at >= now() - interval '10 weeks' GROUP BY 1,2 ORDER BY 1 DESC, 3 DESC""")

q("7. VENTAS: atribución (mu = exacta, email = aproximada, ninguna = sin suscriptor)",
  """SELECT coalesce(nullif(attribution,''),'ninguna') AS atribucion, count(*) AS ventas, round(sum((amount_cents-refunded_cents)/100.0),2) AS eur
       FROM analytics_purchase GROUP BY 1 ORDER BY 2 DESC""")
