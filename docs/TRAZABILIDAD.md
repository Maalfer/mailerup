# Trazabilidad de leads (MailerUp + tienda)

Objetivo: poder responder "¿de dónde vienen los leads, dónde pierden el interés y cuáles compran?" con datos.
Implantado el 2026-09-26. Informe listo: `scripts/informe_embudo.py`.

## Recorrido y dónde queda registrado

| Etapa | Dónde se guarda | Cómo |
|---|---|---|
| Visita a página de captación | `analytics_landingvisit` | beacon JS `POST /t/v/` (solo visitas con señal de marketing o con formulario) |
| Formulario enviado (aún sin confirmar) | `analytics_signupattempt` | `SubscribeView`; `outcome`: pending / confirmed / already_subscribed |
| Alta confirmada + origen first-touch | `subscribers_subscriber` (`source`, `utm_*`, `manychat_sid`, `visitor_id`, `attribution_method`) | `VerifySubscriptionView` copia el origen del intento |
| Entra en secuencia | `automations_automationenrollment` | ya existía |
| Correo enviado por paso | `automations_automationsend` | ya existía |
| Apertura / clic por paso | `analytics_automationemailopen/click` (clic ahora guarda `user_agent`) | ya existía |
| Baja / rebote | `analytics_emailunsubscribe/emailbounce` | ya existía |
| Clic en enlace a la tienda | redirect `/ca/` añade `mu=<id suscriptor>` | `_with_subscriber_id` |
| Compra | `analytics_purchase` (copia de `payments` de la tienda) | `scripts/sync_compras.py`, cron cada 10 min |

## Cómo viaja el origen
1. `static/js/lead-tracking.js` (cargado en `base.html` de la tienda) guarda en localStorage el **primer** toque con señal
   (utm_*, `mcp_token` de ManyChat -> `manychat_sid`/`manychat_pid`, referrer externo) y un `visitor_id` aleatorio.
2. Añade esos datos como campos ocultos a todo `<form action="*/subscribe/*">` y envía el beacon de visita.
   Es JS (no servidor) porque `/newsletter` está cacheada por Cloudflare.
3. `SubscribeView` saneia (`apps/analytics/attribution.py`) y decide `source`: manychat > utm_source > red social por referrer > web.
4. La compra: el enlace del correo lleva `mu=<subscriber_id>` -> sesión de la tienda -> metadata de Stripe -> `payments.mailerup_sid`
   -> `analytics_purchase.mailerup_sid`. Atribución **exacta** (`attribution='mu'`); si no hay `mu`, se casa por email (`'email'`, aproximada).

## Vistas SQL (solo lectura; migración `analytics.0005`)
- `lead_events`: línea de tiempo unificada (form_submitted, confirmed, enrolled, email_sent, email_open, email_click, unsubscribed, bounced, purchase).
- `lead_funnel`: una fila por lead (origen, pasos enviados/abiertos/clicados, último paso abierto, clic en curso, baja, compras, ingresos, tiempo hasta compra).
- `step_funnel`: por automatización, paso y origen: enviados, abren, clic, clic en curso, bajas en 48 h.
- `funnel_by_source`: embudo completo por origen.
- `lead_click_kind(url)`: clasifica el clic (curso / recurso / youtube / comunidad / web / otro).

Ejemplos:
```sql
SELECT * FROM lead_events WHERE email='x@y.com' ORDER BY event_at;      -- toda la historia de un lead
SELECT * FROM step_funnel WHERE source='manychat' ORDER BY step_order;  -- dónde pierden interés los de ManyChat
SELECT * FROM lead_funnel WHERE source='manychat' AND clicked_course AND purchases=0;  -- calientes sin comprar
```

## Cómo etiquetar el contenido de ManyChat (importante)
El enlace del flujo debe llevar parámetros propios para saber QUÉ contenido trae cada lead:
`https://elrincondelhacker.es/newsletter?utm_source=manychat&utm_medium=<reel|story|dm>&utm_campaign=<tema>&utm_content=<id-del-reel>`
ManyChat añade `mcp_token` solo (identifica al contacto, no al contenido). Sin `utm_campaign/utm_content` el origen es "manychat" pero no el reel.

## Limitaciones conocidas
- Leads anteriores al 2026-09-26: `source` vacío ("desconocido"), salvo 98 marcados `manychat` y 52 `web` con `attribution_method='inferred'`
  (reconstruidos por IP/hora desde los logs de nginx; aproximados).
- Ventas anteriores a `mu`: solo atribución por email. Ventas de personas que compran con otro email o sin suscribirse: `ninguna`.
- Aperturas: pueden inflarse (proxies de privacidad de correo). Clics: pueden incluir escáneres; `user_agent` permite filtrarlos.
- Visitas: solo se cuentan las que ejecutan JS y tienen señal de marketing o formulario; visitantes con bloqueador no aparecen.

## Copias previas a este cambio
`/opt/backups-trazabilidad-20260926/` (código de las apps y dump de Postgres `mailerup.pgdump`).

## Enlaces desde DockerLabs (añadido 2026-09-26)
- Botón **Newsletter** (footer de todas las páginas) y botón **Academia** (home) apuntan a `dockerlabs.es/go/<destino>?o=<ubicación>`.
- `/go/` cuenta el clic en la tabla `outbound_click_log` (MariaDB de dockerlabs; sin bots, visitante = hash diario) y redirige (302) a
  `elrincondelhacker.es[/newsletter]?utm_source=dockerlabs&utm_medium=<ubicación>&utm_campaign=<newsletter|academia>`.
- Consulta: `dockerlabs.es/estadisticas` (admin/moderador), tarjeta «Clics hacia elrincondelhacker.es», por día y por botón/ubicación.
- Continuación del embudo: quien llega y se suscribe queda en MailerUp con `source='dockerlabs'`
  (`SELECT * FROM funnel_by_source WHERE source='dockerlabs'`); las compras llevan `utm_source=dockerlabs` en `analytics_purchase`.
- Para añadir otro botón: nuevo destino en `_GO_DESTINOS` (`dockerlabs/routes/pages_core.py`) y enlace `/go/<destino>?o=<ubicación>`.
- Copias previas: `/tmp/claude-5001/.../scratchpad/bak2` (efímero).

## Corrección 2026-09-27: no había cron, se usa systemd timer
Este VPS no tiene demonio `cron` instalado; todo lo periódico va por `systemd timer` (ver `sincronizar-pagos.timer`
como referencia). Los `/etc/cron.d/*` creados el 26/09 (sync_compras y recuperar_carritos) nunca se ejecutaron solos.
Sustituidos por:
- `mailerup-sync-compras.timer` (cada 10 min) → `mailerup-sync-compras.service`
- `elrincondelhacker-carritos.timer` (cada 15 min) → `elrincondelhacker-carritos.service`
Comprobar con: `systemctl list-timers | grep -E "mailerup-sync|carritos"`.
