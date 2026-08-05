# MailerUp MCP

Servidor **MCP (Model Context Protocol)** para administrar toda la plataforma
[MailerUp](../README.md) desde **Claude** (Claude Code, Claude Desktop) u otros
clientes/modelos compatibles con MCP.

Con él puedes, en lenguaje natural: crear y programar campañas, gestionar
suscriptores y grupos, montar automatizaciones y formularios, consultar
analíticas y entregabilidad, administrar usuarios y API keys, y **hacer backups**
— todo contra tu instancia de MailerUp, sin tocar la base de datos a mano.

Habla con la **API REST** de MailerUp usando la misma autenticación que el panel
(**JWT en cookies HttpOnly**, con refresco automático de token). No necesita
acceso al servidor ni a la base de datos: basta la URL pública y unas
credenciales del panel.

---

## Requisitos

- Python 3.10+
- Una instancia de MailerUp accesible por HTTP(S) y una cuenta del panel
  (para gestión total —usuarios, API keys, backup SQLite— usa una cuenta **admin**).

## Instalación

```bash
cd mcp
bash setup.sh          # crea .venv e instala mcp + httpx, y hace una prueba de humo
```

O manualmente:

```bash
cd mcp
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

## Configuración

El servidor se configura por **variables de entorno**:

| Variable | Obligatoria | Descripción |
|---|---|---|
| `MAILERUP_BASE_URL` | ✅ | URL pública de tu MailerUp, p.ej. `https://newsletter.tudominio.com` |
| `MAILERUP_EMAIL` | ✅ | Email de acceso al panel (**el login es por email**, no por usuario) |
| `MAILERUP_PASSWORD` | ✅ | Contraseña del panel |
| `MAILERUP_VERIFY_SSL` | — | `false` para aceptar certificados autofirmados (default `true`) |
| `MAILERUP_TIMEOUT` | — | Timeout HTTP en segundos (default `120`) |
| `MAILERUP_BACKUP_DIR` | — | Carpeta destino de los backups (default `~/mailerup-backups`) |

> Puedes partir del fichero [`.env.example`](.env.example). Las credenciales
> nunca se suben al repo (`.gitignore`).

## Registrar el servidor en Claude Code

Desde la carpeta `mcp/`:

```bash
claude mcp add mailerup \
  -e MAILERUP_BASE_URL=https://newsletter.tudominio.com \
  -e MAILERUP_EMAIL=admin@tudominio.com \
  -e MAILERUP_PASSWORD='tu-contraseña' \
  -- "$(pwd)/.venv/bin/python" -m mailerup_mcp
```

Comprueba con `claude mcp list` y, dentro de Claude Code, con `/mcp`.

## Registrar el servidor en Claude Desktop

Añade esto a tu `claude_desktop_config.json`
(macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`;
Windows: `%APPDATA%\Claude\claude_desktop_config.json`) y reinicia la app:

```json
{
  "mcpServers": {
    "mailerup": {
      "command": "/ruta/absoluta/a/mailerup/mcp/.venv/bin/python",
      "args": ["-m", "mailerup_mcp"],
      "env": {
        "MAILERUP_BASE_URL": "https://newsletter.tudominio.com",
        "MAILERUP_EMAIL": "admin@tudominio.com",
        "MAILERUP_PASSWORD": "tu-contraseña"
      }
    }
  }
}
```

## Ejecutar a mano (para depurar)

```bash
MAILERUP_BASE_URL=... MAILERUP_EMAIL=... MAILERUP_PASSWORD=... \
  ./.venv/bin/python -m mailerup_mcp
```

Se queda escuchando por **stdio** (así es como lo lanza el cliente MCP).

---

## Herramientas disponibles (68)

**Cuenta / ajustes**: `whoami`, `update_account_settings`, `change_password`,
`list_email_providers`, `send_test_email`.

**Usuarios (admin)**: `list_users`, `create_user`, `update_user`, `delete_user`.

**API keys (admin)**: `list_api_keys`, `create_api_key`, `delete_api_key`.

**Grupos**: `list_groups`, `create_group`, `update_group`, `delete_group`.

**Suscriptores**: `list_subscribers`, `add_subscriber`, `update_subscriber`,
`delete_subscriber`, `bulk_delete_subscribers`, `move_subscribers`,
`import_subscribers`, `export_subscribers`, `low_engagement_subscribers`.

**Campañas**: `list_campaigns`, `get_campaign`, `create_campaign`,
`update_campaign`, `delete_campaign`, `send_campaign`, `schedule_campaign`,
`unschedule_campaign`, `pause_campaign`, `resume_campaign`, `send_test_campaign`,
`duplicate_campaign`, `add_campaign_exclusions`, `clear_campaign_exclusions`.

**Recursos / almacenamiento**: `list_resources`, `upload_resource`,
`delete_resource`, `storage_usage`.

**Formularios**: `list_forms`, `get_form`, `create_form`, `update_form`,
`delete_form`, `get_form_embed`.

**Automatizaciones**: `list_automations`, `get_automation`, `create_automation`,
`update_automation`, `delete_automation`, `add_automation_step`,
`update_automation_step`, `delete_automation_step`.

**Analíticas**: `analytics_overview`, `campaign_analytics`,
`automations_overview`, `automation_analytics`, `subscriptions_timeseries`,
`deliverability`, `deliverability_recipients`, `retry_failed_sends`.

**Backups**: `backup_all`, `export_database_sqlite`.

**Escape hatch**: `api_request` (petición cruda para lo que no cubran las demás).

### Sobre los backups

- `backup_all` hace un **backup lógico completo vía API** y funciona con SQLite o
  PostgreSQL: vuelca a una carpeta local el perfil, los grupos, **todos** los
  suscriptores por grupo (CSV importable + recuentos), las campañas completas
  (incluido el HTML), automatizaciones, formularios, recursos y analíticas.
  Los CSV se pueden reimportar con `import_subscribers`.
- `export_database_sqlite` descarga el fichero SQLite entero, pero **solo**
  funciona si el servidor usa SQLite (desarrollo). En producción con PostgreSQL
  usa `backup_all` para el backup lógico, o `pg_dump` en el servidor para un
  volcado binario completo (ver `deploy/` y `update.sh` del repo).

---

## Ejemplos de peticiones a Claude

- «Crea un grupo "Clientes 2026" e impórtale los emails de este CSV.»
- «Redacta una campaña de bienvenida en HTML, mándamela como prueba a mi correo
  y, si me gusta, prográmala para el lunes a las 9:00.»
- «¿Qué campaña tuvo mejor tasa de apertura este mes? Enséñame los enlaces más
  clicados.»
- «Monta una automatización de 3 pasos enganchada al formulario de la landing.»
- «Haz un backup completo antes de que toque nada.»

## Cómo funciona la autenticación

MailerUp autentica la API privada **solo por cookie JWT**
(`CookieJWTAuthentication`), no por `Authorization: Bearer`. El cliente
(`mailerup_mcp/client.py`) hace login en `POST /api/auth/token/` con tu email y
contraseña (fija las cookies `access`/`refresh`), reutiliza el *cookie jar* y,
ante un 401, refresca con `POST /api/auth/token/refresh/` y reintenta; si el
refresh falla, vuelve a loguearse. Los secretos (contraseña SMTP, API keys de
Brevo/SendGrid) nunca se leen de vuelta: la API solo expone flags `*_set`.

## Seguridad

- Trata `MAILERUP_PASSWORD` como un secreto: pásalo por variable de entorno del
  cliente MCP, no lo escribas en ficheros versionados.
- El MCP tiene los mismos permisos que la cuenta que uses. Para tareas de solo
  lectura o de un único negocio, usa una cuenta con los permisos mínimos.
- Las operaciones destructivas (`delete_*`, `bulk_delete_subscribers`,
  `send_campaign`) hacen exactamente lo que dicen: revisa lo que pides a Claude
  antes de confirmar envíos o borrados masivos.
