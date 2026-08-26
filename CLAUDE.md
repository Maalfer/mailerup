# CLAUDE.md

Guía operativa para asistentes IA (Claude Code y similares) que trabajen en este repo.

## Resumen del proyecto

MailerUp es una plataforma autoalojada de newsletter (estilo MailerLite) escrita en **Django 6 + DRF** (backend) y **React 19 + Vite + Tailwind + Tiptap** (frontend). Usa un scheduler in-process (sin Redis ni Celery worker). Pensada para una VPS modesta con SMTP del hosting (Raiola, Gmail, IONOS…) o Postfix local.

> **Despliegue NATIVO (sin Docker) desde 2026-06-15.** El proyecto se ejecutaba antes con Docker Compose; se migró a un despliegue nativo sobre la VPS. Los ficheros `docker-compose.yml`, `DOCKER.md`, `backend/Dockerfile` y `nginx/Dockerfile` quedan como **legado/referencia** y **no** describen el despliegue actual.

## Arquitectura de despliegue actual (producción: `newsletter.example.com`)

VPS Ubuntu 24.04, **1 GB RAM / 1 CPU** (con swapfile de 2 GB). Código en `/opt/mailerup`.

- **PostgreSQL 16 nativo** en `127.0.0.1:5432` (BD `mailerup`, rol `mailerup`). La app conecta por `DATABASE_URL` (en `backend/.env`).
- **App Django** como servicio **systemd `mailerup.service`**:
  `/opt/mailerup/backend/venv/bin/uvicorn mailerup.asgi:application --host 127.0.0.1 --port 8100 --workers 1`
  (**1 worker** a propósito: el scheduler in-process debe correr en una única instancia). venv en `/opt/mailerup/backend/venv`, `DJANGO_SETTINGS_MODULE=mailerup.settings.production`.
- **nginx del HOST** (no contenedor) sirve el SPA y hace de proxy. Vhost `/etc/nginx/sites-available/newsletter.example.com`:
  `root /var/www/mailerup/dist`, `client_max_body_size 25M`,
  `location ~ ^/(api|admin|static|u|o|c|oa|ca|subscribe|verify-subscription|recurso)(/|$)` → `proxy_pass http://127.0.0.1:8100` (con `X-Forwarded-Proto https`),
  resto → `try_files $uri $uri/ /index.html`. TLS por **Cloudflare Origin cert**. (El mismo nginx sirve otros vhosts del correo — no tocarlos.)
- **Static**: whitenoise (servido por uvicorn vía `/static/`). **Media** (adjuntos de campañas): `/opt/mailerup/backend/media/resources/`.
- **`backend/.env`** (gitignored): secretos Django + `DATABASE_URL=postgres://…@127.0.0.1:5432/mailerup` + `SMTP_HOST=127.0.0.1` (Postfix del host) + `ALLOWED_HOSTS`, `PUBLIC_BASE_URL`, `CSRF_TRUSTED_ORIGINS`, etc. Hay `backend/.env.example`. Cualquier variable nueva debe tener default en `settings/base.py`.

## Despliegue y actualización (LO MÁS IMPORTANTE)

El repo **no tiene CI ni push automático** a la VPS. Para desplegar un cambio:

### Backend (código Python / migraciones)
```bash
# en la VPS, /opt/mailerup (tras sincronizar el código: git pull o rsync)
cd /opt/mailerup/backend
venv/bin/pip install -r requirements.txt            # solo si cambió requirements.txt
DJANGO_SETTINGS_MODULE=mailerup.settings.production venv/bin/python manage.py migrate --noinput
DJANGO_SETTINGS_MODULE=mailerup.settings.production venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart mailerup
```
O usa el script `bash /opt/mailerup/update.sh` (versión nativa: sincroniza git, pip, migrate, collectstatic, reinicia el servicio — **NO** toca el frontend).

### Frontend (React/Vite)
**Compila SIEMPRE en local / fuera de la VPS** y sube el `dist/`:
```bash
# en tu máquina
cd frontend && npm ci && npm run build
rsync -az --delete frontend/dist/  usuario@vps:/var/www/mailerup/dist/
```
> ⚠️ **NUNCA compiles el frontend (Vite/npm) en la VPS.** Con 1 GB de RAM el build agota la memoria y cuelga la máquina (OOM). Por eso el build es local y solo se sube el `dist`.

### Comandos útiles
```bash
systemctl status mailerup                 # estado del servicio
journalctl -u mailerup -f                 # logs de la app
sudo systemctl restart mailerup           # reiniciar tras cambios de código
DJANGO_SETTINGS_MODULE=mailerup.settings.production venv/bin/python manage.py shell
DJANGO_SETTINGS_MODULE=mailerup.settings.production venv/bin/python manage.py createsuperuser
# Backup de BD:
pg_dump -Fc -h 127.0.0.1 -U mailerup mailerup > /opt/mailerup/backups/mailerup_$(date +%F).dump

# Desarrollo local (opcional): settings de development con SQLite
cd backend && python manage.py runserver  # DJANGO_SETTINGS_MODULE=mailerup.settings.development
```

## Arquitectura — lo que necesitas saber para no romper nada

### Backend

- **Apps activas**: `accounts`, `subscribers`, `campaigns`, `analytics`, `integrations`, `forms` (label `subscription_forms`), `automations`.
- **Settings**: `mailerup/settings/{base,development,production}.py`. `production` y `development` activan `CELERY_TASK_ALWAYS_EAGER=True` (las tareas Celery corren en el mismo hilo, sin Redis). `production` confía en `X-Forwarded-Proto` (TLS lo termina nginx/Cloudflare) y fuerza `SECURE_SSL_REDIRECT`.
- **Modelo `User`** (`apps/accounts/models.py`): extiende `AbstractUser`. SMTP (`email_provider`, `smtp_*`, `brevo_api_key`, `sendgrid_api_key`), pie de correo (`footer_*`), remitente (`from_name`, `from_email`). **Rol admin = `is_staff=True`** (el serializer lo expone como `is_admin`). Datos compartidos entre usuarios vía `get_admin_user()`.
- **Grupos de suscriptores**: `subscribers.SubscriberList` = "grupo". `Subscriber` pertenece a UNA lista (FK `list`, `unique_together(list,email)`). Cada `forms.SubscriptionForm` tiene `target_list` (a qué grupo entran los suscriptores; fallback a `_get_or_create_default_list`). CRUD de grupos en `/api/subscribers/groups/`; `all_subscribers`/`export`/`import`/`add` aceptan `?list=` (sin él = todos los grupos).
- **`Campaign`**: estados `draft|scheduled|sending|sent|paused`. Destinatarios: un grupo (`subscriber_list`) o `send_to_all=True` (todos los grupos, deduplicando por email con `DISTINCT ON` de Postgres en `_pending_subscribers`).
- **Automatizaciones** (`apps/automations/`): `Automation` → `AutomationStep` (PK UUID) → `AutomationEnrollment`/`AutomationSend`. El scheduler dispara `process_automation_queue` cada 30-60s. Cada paso inyecta pixel de apertura (`/oa/<token>/`) y reescribe enlaces (`/ca/<token>/`). Métricas en `analytics.AutomationEmailOpen/Click`.
- **Scheduler + envío progresivo**: `apps/campaigns/scheduler.py` arranca un hilo daemon en `apps.py.ready()` (solo en procesos servidor). Envía por lotes (`CAMPAIGN_SEND_BATCH_SIZE`, `CAMPAIGN_SEND_INTERVAL_SECONDS`), estado reanudable en `CampaignSend` con `get_or_create`. `MAILERUP_DISABLE_SCHEDULER=1` lo desactiva (útil si algún día hay >1 proceso).
- **Envío** (`apps/campaigns/tasks.py`): `_personalize()` sustituye placeholders, reescribe `href=` para click tracking y añade el pixel. **Tokens firmados con `signing.dumps`**; los URLs públicos (`/u/`, `/o/`, `/c/`, `/oa/`, `/ca/`) viven en `mailerup/urls.py`. `SMTPSender` (`apps/integrations/email_sender.py`) fuerza `from_addr`/`to_addrs` explícitos para que el envelope MAIL FROM coincida con `smtp_user` (clave para SPF). **No tocar sin saber lo que haces.**
- **Permisos** (ver sección "Modelo de seguridad" más abajo): el default DRF es `IsAuthenticated` (`settings/base.py`), así que **toda la API es privada salvo opt-in explícito**. `IsAdminUser` protege además `/api/auth/users/*` (alta/gestión de cuentas) y `/api/auth/db-export/`. `UserSerializer.update()` filtra los campos `ADMIN_ONLY_FIELDS` para no-admins; estos heredan provider/footer del primer admin pero **nunca** sus secretos. **No existe registro anónimo**: las cuentas solo las crea un admin o `createsuperuser`.

### Modelo de seguridad (PRIORIDAD MÁXIMA — no romper estos invariantes)

MailerUp es un **inquilino compartido**: existe un usuario admin (`is_staff=True`) y los datos
(suscriptores, campañas, formularios, automatizaciones) pertenecen a ese admin vía
`get_admin_user()`. Todos los usuarios **autenticados** comparten lectura/escritura de la
newsletter, los suscriptores y las campañas — eso es intencionado. Las reglas inviolables:

1. **Nadie se registra solo.** No hay endpoint público de alta. Las cuentas las crea únicamente
   un admin en `POST /api/auth/users/` (`IsAdminUser`) o `manage.py createsuperuser`. **Nunca**
   reintroducir un `RegisterView`/ruta `register` con `AllowAny` (fue el CVE-2026-13164).
2. **Sin autenticación no se accede a ningún dato privado.** El default DRF es `IsAuthenticated`.
   Los únicos endpoints `AllowAny` legítimos son: login/refresh/logout, el alta pública de
   suscriptores (`/subscribe/…`, solo **recibe** datos), los públicos firmados por token HMAC
   (tracking `/o /c /oa /ca`, baja `/u`, confirmación de alta) y `/recurso/<uuid+ext>/`
   (`serve_resource`, sin firma — el control es que el nombre es un UUID4 no adivinable, no un
   token verificado; no subir ahí nada que no deba ser público conociendo su URL). **Cualquier
   vista nueva que liste o exponga datos debe heredar `IsAuthenticated` (no poner `AllowAny`).**
3. **Solo el admin ve/edita las API keys y credenciales de proveedor.** `brevo_api_key`,
   `sendgrid_api_key` y `smtp_password` son `write_only` en `UserSerializer` (nunca se devuelven
   en `GET /api/auth/me/`; la UI solo recibe flags `*_set`). Los campos `ADMIN_ONLY_FIELDS`
   (provider/SMTP/footer) solo los modifica un admin; un no-admin los hereda en lectura pero
   `UserSerializer.update()` los descarta si intenta escribirlos. Las credenciales SMTP viven en
   `.env`, no en la BD.
4. **Escalada de privilegios cerrada.** `MeView` tiene `email`/`is_admin` en `read_only_fields`:
   un usuario no puede auto-otorgarse admin ni cambiar su email. Solo `IsAdminUser` toca `is_staff`.
   No se puede borrar/degradar al último admin ni autoeliminarse.
5. **Aislamiento por propietario en los serializers.** Los campos relacionales editables
   (`Campaign.subscriber_list`, `SubscriptionForm.target_list`) acotan su queryset al propietario
   en `get_fields()` para evitar IDOR (CWE-639). Replica ese patrón en cualquier `PrimaryKeyRelatedField` nuevo.
6. **Entrada pública siempre escapada.** Datos controlables por el usuario (nombre/email de
   suscriptor, `title`/`description`/`button_text`/`primary_color` de formularios, `success_message`)
   se escapan con `django.utils.html.escape` antes de interpolarse en HTML (correos, páginas de
   baja/confirmación, snippet `embed`). El color se valida contra hex estricto.
7. **No inyectar en `.env`.** `apps/accounts/env_file.update_env()` solo acepta claves de una
   allowlist (`SMTP_*`) y rechaza valores con `\n`/`\r`. No ampliar la allowlist a claves sensibles
   (SECRET_KEY, DATABASE_URL…) ni quitar la validación anti-salto-de-línea.
8. **Rate-limiting.** Login (`scope "login"`, 10/min) y alta pública (`scope "subscribe"`, 30/min)
   usan `ScopedRateThrottle`. El resto de la API autenticada no se limita (hay operaciones masivas
   legítimas). Para limitar un endpoint nuevo, dale `throttle_scope` y añade su rate en
   `DEFAULT_THROTTLE_RATES`.

Antes de mergear cualquier cambio que toque vistas, permisos, serializers o el modelo `User`,
verifica que estos 8 invariantes siguen en pie.

### Frontend

- **Router**: `src/App.jsx` (`RequireAuth` para `Layout`, `RequireAdmin` para `/users`).
- **Auth**: `src/auth.jsx` (user/login/logout). **API**: `src/api.js` (Axios + auto-refresh JWT, `baseURL: '/api'`).
- **Páginas**: `pages/{Login, Layout, Subscribers, Campaigns, CampaignEditor, Analytics, Settings, Users, Automations, AutomationStepEditor, Forms, Deliverability, Storage}.jsx`.
- **Editor**: `components/RichTextEditor.jsx` (Tiptap). **DNS guide**: `components/DnsSetupBlock.jsx`.
- **Tema oscuro**: clase `dark` (Tailwind `darkMode: 'class'`). La paleta `primary` en `tailwind.config.js` define los tonos 50–900; usa `dark:text-white` en estados activos.

## Decisiones a respetar

1. **Postgres en producción** (nativo, `127.0.0.1:5432`, vía `DATABASE_URL`). SQLite solo para desarrollo local.
2. **Sin Redis**. Celery en EAGER; el scheduler usa `threading.Thread`. **1 worker** de uvicorn.
3. **Tokens públicos firmados**. Nunca expongas UUIDs de Subscriber/Campaign/Step en URLs de emails — usa `make_unsubscribe_token` / `make_track_token` / `make_auto_track_token`.
4. **Settings de proveedor compartidos**: solo admins editan provider/SMTP/footer y las **API keys (Brevo/SendGrid) y la contraseña SMTP**; los usuarios normales heredan la config (no los secretos) vía `get_sender()`. Las keys son `write_only`: nunca se devuelven en lecturas.
5. **`from_email` alineado con `smtp_user`** (la UI lo auto-sincroniza y el sender lo fuerza). No revertir.
6. **Roles**: usar `is_staff`. No introducir un campo `role` separado.
7. **Seguridad por defecto**: API privada (`IsAuthenticated`), sin registro anónimo, entrada pública escapada. Los 8 invariantes de la sección "Modelo de seguridad" son la **prioridad máxima** del proyecto.

## Cosas que NO hacer

- No compilar el frontend en la VPS (OOM con 1 GB). Build local + subir `dist`.
- No exponer `db.sqlite3` ni `backend/.env` en commits (comprobado en `.gitignore`).
- No reintroducir envío de campañas inline en el thread del request HTTP. El envío es **progresivo por lotes** vía el scheduler.
- Las **credenciales SMTP se guardan en `.env`** (no en la BD): se escriben con `update_env()` y se leen con `smtp_config_from_env()` (`apps/integrations/email_sender.py`). No volver a persistir `smtp_password` en la BD.
- La app arranca por **ASGI** (`mailerup.asgi:application`). `wsgi.py` se mantiene por compatibilidad.
- **Seguridad (ver "Modelo de seguridad")**: no reabrir el registro anónimo; no poner `AllowAny` en vistas que expongan datos; no devolver `brevo_api_key`/`sendgrid_api_key`/`smtp_password` en lecturas (mantener `write_only`); no quitar el escaping de entrada pública ni la validación anti-inyección de `update_env`.

## Reglas de cambios — OBLIGATORIO

### Migraciones (no negociables)
1. **Solo cambios aditivos por release**: campos nuevos con `default=`/`blank=True`, tablas nuevas. Nunca eliminar/renombrar en el mismo commit que quita el código que los usa.
2. **Renombrar columna = dos releases** (deja de usarla en N, la borra en N+1).
3. **Ejecuta `makemigrations` antes de desplegar** si tocas modelos; verifica `default=`/`blank=True` en campos nuevos. El despliegue hace `migrate` explícito.
4. **Nunca `squashmigrations`** sin avisar.

### Dependencias
5. **Dependencia Python nueva** → `requirements.txt` (y `venv/bin/pip install -r requirements.txt` al desplegar).
6. **Paquete npm nuevo** → `package.json` + `package-lock.json` (entra en el build local del frontend). Mantén el lockfile sincronizado.
7. **No eliminar paquetes** sin verificar que nada los importa.

### API y frontend
8. **No romper endpoints existentes**: mantén campos antiguos como alias o vacíos.
9. **Campos nuevos en serializers**: `read_only` o `required=False`.
10. **Variables de entorno nuevas**: default sensato en `settings/base.py` (`env("VAR", default=...)`) y documentadas en `backend/.env.example`.
11. **`tailwind.config.js`**: si añades clases con tonos de color, asegúrate de que el tono existe en la paleta.

### Checklist antes de desplegar cambios de modelo
```bash
cd backend && python manage.py makemigrations          # genera fichero nuevo
python manage.py migrate                               # aplica sin error (local con SQLite)
python manage.py check                                 # 0 issues
# Verifica default=/blank=True en los campos nuevos
```

## Test mínimo después de cambios grandes
```bash
cd /opt/mailerup/backend
DJANGO_SETTINGS_MODULE=mailerup.settings.production venv/bin/python manage.py check   # 0 issues
sudo systemctl restart mailerup
curl -s -o /dev/null -w "home %{http_code}\n" -H 'X-Forwarded-Proto: https' http://127.0.0.1:8100/   # 404 = ok (la raíz la sirve nginx)
curl -s -o /dev/null -w "api  %{http_code}\n" -H 'X-Forwarded-Proto: https' http://127.0.0.1:8100/api/analytics/overview/   # 401 sin auth = OK
# Seguridad: el registro anónimo NO existe y los datos privados requieren auth
curl -s -o /dev/null -w "register %{http_code}\n" -X POST -H 'X-Forwarded-Proto: https' http://127.0.0.1:8100/api/auth/register/   # 404 = OK (no hay alta pública)
curl -s -o /dev/null -w "subs %{http_code}\n" -H 'X-Forwarded-Proto: https' http://127.0.0.1:8100/api/subscribers/all/   # 401 sin auth = OK
# End-to-end (a través de nginx/Cloudflare):
curl -s -o /dev/null -w "site %{http_code}\n" https://newsletter.example.com/   # 200
```
