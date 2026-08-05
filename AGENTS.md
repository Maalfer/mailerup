# AGENTS.md

Convención reciente (Cursor, OpenAI Codex, Cline, etc.): los agentes leen este archivo para entender el repo. Mantiene paridad con `CLAUDE.md` pero más compacto.

## ¿Qué es Mailerup?

App web autoalojada de newsletter: suscriptores, editor WYSIWYG, envío SMTP/API, tracking, programación, analíticas (campañas y automatizaciones), roles admin/usuario.

## Stack

- Backend: Django 6 + DRF + **PostgreSQL** + JWT (cookies HttpOnly), scheduler in-process (sin Redis).
- Frontend: React 19 + Vite + Tailwind + Tiptap.
- Envío: SMTP (preset por proveedor) o APIs Brevo/SendGrid.
- **Despliegue: NATIVO** (PostgreSQL + systemd/uvicorn + nginx del host). Desde **2026-06-15** ya **no** se usa Docker: `docker-compose.yml`, `DOCKER.md` y los `Dockerfile` quedan como **legado/referencia** (no describen el despliegue actual). Ver `deploy/README.md`.

## Despliegue y actualización (clave)

Producción en `/opt/mailerup` (VPS Ubuntu, 1 GB RAM + swap). App como servicio systemd `mailerup.service` (`uvicorn mailerup.asgi:application`, **1 worker**, `127.0.0.1:8100`), PostgreSQL 16 nativo, nginx del host sirve el SPA (`frontend/dist`) y hace proxy a uvicorn.

```bash
# Backend (en la VPS): sincroniza repo, pip, migrate, collectstatic, reinicia el servicio.
bash /opt/mailerup/update.sh          # hace pg_dump de backup antes de actualizar
DJANGO_SETTINGS_MODULE=mailerup.settings.production /opt/mailerup/backend/.venv/bin/python manage.py createsuperuser

# Frontend: COMPILA EN LOCAL y sube el dist (NUNCA compiles Vite en la VPS: 1 GB RAM → OOM).
cd frontend && npm ci && npm run build
rsync -az --delete frontend/dist/ usuario@vps:/opt/mailerup/frontend/dist/
```

- El código se despliega **desde GitHub**: `update.sh` hace `git pull --ff-only origin <rama>`. **Todo cambio debe commitearse y pushearse a `origin/main`** o no llegará a la VPS.
- **`backend/.env`** (gitignored, uno por VPS): secretos Django + `DATABASE_URL=postgres://…@127.0.0.1:5432/mailerup` + `SMTP_*` (Postfix del host, `SMTP_HOST=127.0.0.1`) + `ALLOWED_HOSTS`, `PUBLIC_BASE_URL`, `CSRF_TRUSTED_ORIGINS`. Variables nuevas → default en `settings/base.py` + documentar en `backend/.env.example`.
- Las **credenciales SMTP viven en `.env`** (no en la BD): se escriben con `update_env()` (allowlist `SMTP_*`, rechaza `\n`/`\r`) y se leen con `smtp_config_from_env()`.
- El `.env` de la raíz (POSTGRES_*, NGINX_HOST_PORT) es **legado de Docker**; en nativo no se usa.
- Desarrollo local: `cd backend && python manage.py runserver` (settings `development`, SQLite).

## Mapa de apps Django

| App            | Responsabilidad                                                                             |
| -------------- | ------------------------------------------------------------------------------------------- |
| `accounts`     | Auth JWT por cookie, roles (`is_staff`), CRUD usuarios admin, API keys, presets proveedor+DNS |
| `subscribers`  | **Grupos** (`SubscriberList`) y suscriptores (uno por grupo), import/export CSV, mover/bulk  |
| `campaigns`    | CRUD campañas, send/schedule/pause/resume/duplicate, A/B, exclusiones, scheduler + recursos  |
| `analytics`    | Tracking open/click (campañas y automatizaciones) + unsubscribe firmado, KPIs, entregabilidad|
| `automations`  | Secuencias por formulario: pasos, enrolamientos, envíos y métricas por paso                  |
| `integrations` | `SMTPSender`, `BrevoSender`, `SendGridSender`, `NullSender` (`get_sender`)                    |
| `forms`        | Formularios de suscripción (label `subscription_forms`) + doble opt-in / verificación        |

**Inquilino compartido**: los datos cuelgan del primer admin (`get_admin_user()`); los usuarios autenticados comparten suscriptores/campañas (intencionado).

## Modelo de seguridad (PRIORIDAD MÁXIMA — no romper)

Los 8 invariantes están en `CLAUDE.md`. En resumen:

1. **Nadie se registra solo**: sin endpoint público de alta; las cuentas las crea un admin (`POST /api/auth/users/`, `IsAdminUser`) o `createsuperuser`. Nunca reintroducir `register`/`AllowAny`.
2. **API privada por defecto** (`IsAuthenticated`). Los únicos `AllowAny` legítimos: login/refresh/logout, alta pública de suscriptores (`/subscribe`, solo recibe), públicos firmados (`/u /o /c /oa /ca`, confirmación, `/recurso`).
3. **Secretos `write_only`**: `smtp_password`, `brevo_api_key`, `sendgrid_api_key` nunca se devuelven (solo flags `*_set`). Provider/SMTP/footer solo los edita un admin.
4. **Escalada cerrada**: `email`/`is_admin` read-only en `MeView`; no borrar/degradar al último admin.
5. **Aislamiento por propietario** en serializers (queryset acotado en `get_fields()`, evita IDOR/CWE-639).
6. **Entrada pública siempre escapada** (`django.utils.html.escape`); color validado a hex.
7. **No inyectar en `.env`** (allowlist `SMTP_*`, sin saltos de línea).
8. **Rate-limiting** por `throttle_scope` (login 10/min, subscribe 30/min).

## Reglas que respetar

1. **Postgres en prod** (vía `DATABASE_URL`); SQLite solo en local. **Sin Redis** (Celery EAGER + thread scheduler); uvicorn con **1 worker** (el scheduler in-process debe correr en una única instancia).
2. **Tokens públicos firmados** con `django.core.signing`. Nunca exponer UUIDs en URLs de email (`make_*_token`).
3. **`from_email` alineado con `smtp_user`** (UI auto-sincroniza, `SMTPSender` lo fuerza a nivel envelope).
4. **Provider/footer compartidos**: los configura el primer admin; no-admins heredan la config (no los secretos) vía `get_sender()`.
5. **Roles**: `is_staff` = admin (`RequireAdmin` front + `IsAdminUser` back). No introducir un campo `role`.
6. **Datos sensibles fuera del repo**: `backend/.env`, `.env` raíz, `db.sqlite3` ignorados.

## Compatibilidad con `update.sh` (obligatorio)

- Migraciones **solo aditivas** por release (campos con `default=`/`blank=True`, tablas nuevas). Renombrar = dos releases. Nunca `squashmigrations` sin avisar.
- Dependencia Python nueva → `requirements.txt`. Paquete npm nuevo → `package.json` + `package-lock.json` sincronizado (si no, `npm ci` rompe el build local).
- No romper endpoints/serializers existentes (campos nuevos `read_only`/`required=False`).
- Variables de entorno nuevas → default en `settings/base.py` + documentar en `backend/.env.example`.
- **Si añades o cambias endpoints de la API, refléjalo en las herramientas del MCP** (`mcp/mailerup_mcp/server.py`) para mantener la paridad.

## Servidor MCP (`mcp/`)

Herramienta **cliente** (no forma parte del runtime del servidor ni lo despliega `update.sh`): un servidor MCP en Python (paquete `mailerup_mcp`, venv propio) que expone la API como herramientas para administrar MailerUp desde Claude u otros modelos. Habla con la API REST usando el **mismo login por cookie JWT** (`POST /api/auth/token/` con `email`+`password`, refresco automático). Config por entorno: `MAILERUP_BASE_URL`, `MAILERUP_EMAIL`, `MAILERUP_PASSWORD`. Ver `mcp/README.md`.

## Antes de hacer commit

- `python manage.py check` → 0 issues (en la VPS: `DJANGO_SETTINGS_MODULE=mailerup.settings.production .venv/bin/python manage.py check`).
- Si tocas modelos: `python manage.py makemigrations` (verifica `default=`/`blank=True`).
- Verificar que no se cuela `.env`, `db.sqlite3` ni `node_modules` (`git status`).
- **Commit + push a `origin/main`** (fuente de verdad del despliegue).

## Documentación adicional

- `deploy/README.md` — **despliegue NATIVO actual** (systemd + nginx del host + Postgres nativo).
- `CLAUDE.md` — contexto operativo extenso para asistentes IA (incluye los 8 invariantes de seguridad).
- `mcp/README.md` — servidor MCP para administrar la plataforma desde Claude.
- `README.md` — público (capturas, funcionalidades).
- `DOCKER.md` / `docker-compose.yml` / `*/Dockerfile` — **legado** (despliegue anterior con Docker; no vigente).
