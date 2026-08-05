"""Servidor MCP de MailerUp — administración total de la plataforma.

Ejecuta ``python -m mailerup_mcp`` (o el script ``mailerup-mcp``). Se comunica
por stdio con el cliente MCP (Claude Code / Claude Desktop / etc.).

Configuración por variables de entorno:
  MAILERUP_BASE_URL   URL pública (p.ej. https://newsletter.example.com)
  MAILERUP_EMAIL      email de acceso al panel (el login es por email)
  MAILERUP_PASSWORD   contraseña del panel
  MAILERUP_VERIFY_SSL "false" para saltarse verificación TLS (default: true)
  MAILERUP_TIMEOUT    timeout HTTP en segundos (default: 120)
  MAILERUP_BACKUP_DIR carpeta destino de los backups (default: ~/mailerup-backups)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# El servidor de alto nivel se llama `FastMCP` en el SDK 1.x y `MCPServer` en el
# 2.x; ambos exponen el mismo `.tool()` / `.run()`. Soportamos las dos versiones.
try:  # SDK mcp >= 2.0
    from mcp.server import MCPServer as _Server
except ImportError:  # SDK mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server

from .client import MailerUpClient, MailerUpError

mcp = _Server("mailerup")

_client: MailerUpClient | None = None


def client() -> MailerUpClient:
    global _client
    if _client is None:
        _client = MailerUpClient()
    return _client


def _clean(d: dict) -> dict:
    """Quita las claves con valor None (para PATCH/POST parciales)."""
    return {k: v for k, v in d.items() if v is not None}


def _as_listing(items: Any) -> Any:
    """Envuelve una lista en {"count": N, "items": [...]} para una salida clara
    y con total. Si no es una lista, la devuelve tal cual."""
    if isinstance(items, list):
        return {"count": len(items), "items": items}
    return items


async def _collect(path: str, params: dict | None = None) -> Any:
    """GET que devuelve la lista COMPLETA.

    Los endpoints de lista de DRF vienen paginados ({count, next, previous,
    results}, 25/página). Este helper sigue las páginas y devuelve todos los
    elementos. Si la respuesta no es una lista paginada estándar, la devuelve
    tal cual (p.ej. /subscribers/all/, que tiene su propia paginación explícita).
    """
    params = dict(params or {})
    first = await client().get(path, params={**params, "page": 1})
    if not (isinstance(first, dict) and "results" in first and "next" in first):
        return first
    items = list(first["results"])
    count = first.get("count", len(items))
    page = 2
    while len(items) < count:
        chunk = await client().get(path, params={**params, "page": page})
        res = chunk.get("results") if isinstance(chunk, dict) else None
        if not res:
            break
        items.extend(res)
        page += 1
    return items


def _backup_dir() -> Path:
    raw = os.environ.get("MAILERUP_BACKUP_DIR") or "~/mailerup-backups"
    return Path(raw).expanduser()


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


# ===========================================================================
# CUENTA / AJUSTES
# ===========================================================================

@mcp.tool()
async def whoami() -> Any:
    """Devuelve el perfil y ajustes de la cuenta autenticada (GET /api/auth/me/).

    Incluye rol (is_admin), remitente (from_name/from_email), proveedor de email,
    config SMTP no secreta y pie de correo. Los secretos (contraseña SMTP, API
    keys de Brevo/SendGrid) NUNCA se devuelven: solo los flags *_set.
    """
    return await client().get("/api/auth/me/")


@mcp.tool()
async def update_account_settings(
    from_name: str | None = None,
    from_email: str | None = None,
    company: str | None = None,
    timezone_name: str | None = None,
    email_provider: str | None = None,
    smtp_host: str | None = None,
    smtp_port: int | None = None,
    smtp_user: str | None = None,
    smtp_password: str | None = None,
    smtp_use_tls: bool | None = None,
    smtp_use_ssl: bool | None = None,
    brevo_api_key: str | None = None,
    sendgrid_api_key: str | None = None,
    footer_company: str | None = None,
    footer_address: str | None = None,
    footer_unsubscribe_text: str | None = None,
    footer_button_label: str | None = None,
    footer_forward_text: str | None = None,
    footer_subscribe_text: str | None = None,
    send_rate_per_hour: int | None = None,
) -> Any:
    """Actualiza ajustes de la cuenta (PATCH /api/auth/me/).

    Los campos de proveedor/SMTP/pie y las API keys solo los aplica un admin;
    un usuario normal los hereda del admin y el servidor descarta esos campos si
    intenta escribirlos. `email` y el rol admin no se pueden cambiar aquí.
    Las credenciales SMTP se guardan en el `.env` del servidor, no en la BD.
    """
    payload = _clean({
        "from_name": from_name,
        "from_email": from_email,
        "company": company,
        "timezone": timezone_name,
        "email_provider": email_provider,
        "smtp_host": smtp_host,
        "smtp_port": smtp_port,
        "smtp_user": smtp_user,
        "smtp_password": smtp_password,
        "smtp_use_tls": smtp_use_tls,
        "smtp_use_ssl": smtp_use_ssl,
        "brevo_api_key": brevo_api_key,
        "sendgrid_api_key": sendgrid_api_key,
        "footer_company": footer_company,
        "footer_address": footer_address,
        "footer_unsubscribe_text": footer_unsubscribe_text,
        "footer_button_label": footer_button_label,
        "footer_forward_text": footer_forward_text,
        "footer_subscribe_text": footer_subscribe_text,
        "send_rate_per_hour": send_rate_per_hour,
    })
    return await client().patch("/api/auth/me/", json=payload)


@mcp.tool()
async def change_password(current_password: str, new_password: str) -> Any:
    """Cambia la contraseña de la cuenta actual (mínimo 8 caracteres)."""
    return await client().post(
        "/api/auth/change-password/",
        json={"current_password": current_password, "new_password": new_password},
    )


@mcp.tool()
async def list_email_providers() -> Any:
    """Lista los ~20 proveedores de email preconfigurados (host/puerto/TLS y
    presets DNS de SPF/DKIM/DMARC por proveedor)."""
    return _as_listing(await client().get("/api/auth/email-providers/"))


@mcp.tool()
async def send_test_email(to: str | None = None) -> Any:
    """Envía un email de prueba con el proveedor configurado. Si no indicas `to`,
    se envía al email de la cuenta. Devuelve diagnóstico (auth, SPF, dominio…)."""
    return await client().post("/api/auth/test-email/", json=_clean({"to": to}))


# ===========================================================================
# USUARIOS (admin) y API KEYS (admin)
# ===========================================================================

@mcp.tool()
async def list_users() -> Any:
    """[admin] Lista TODAS las cuentas del panel (GET /api/auth/users/)."""
    return _as_listing(await _collect("/api/auth/users/"))


@mcp.tool()
async def create_user(
    username: str,
    email: str,
    password: str | None = None,
    company: str | None = None,
    is_admin: bool = False,
) -> Any:
    """[admin] Crea una cuenta de panel. Si no das contraseña, se usa 'changeme123'.
    `is_admin=True` la marca como administradora (is_staff)."""
    payload = _clean({
        "username": username,
        "email": email,
        "password": password,
        "company": company,
        "is_admin": is_admin,
    })
    return await client().post("/api/auth/users/", json=payload)


@mcp.tool()
async def update_user(
    user_id: int,
    username: str | None = None,
    email: str | None = None,
    company: str | None = None,
    password: str | None = None,
    is_admin: bool | None = None,
) -> Any:
    """[admin] Modifica una cuenta. No se puede quitar el rol admin al último admin."""
    payload = _clean({
        "username": username,
        "email": email,
        "company": company,
        "password": password,
        "is_admin": is_admin,
    })
    return await client().patch(f"/api/auth/users/{user_id}/", json=payload)


@mcp.tool()
async def delete_user(user_id: int) -> Any:
    """[admin] Elimina una cuenta. No puedes eliminarte a ti mismo ni al último admin."""
    return await client().delete(f"/api/auth/users/{user_id}/", expect="none")


@mcp.tool()
async def list_api_keys() -> Any:
    """[admin] Lista TODAS las API keys del endpoint externo de alta de suscriptores."""
    return _as_listing(await _collect("/api/auth/api-keys/"))


@mcp.tool()
async def create_api_key(name: str) -> Any:
    """[admin] Crea una API key para `POST /api/public/subscribers/`.

    ⚠️ La clave en claro se devuelve UNA sola vez (campo `key`); guárdala, no se
    puede recuperar después (solo se almacena su hash)."""
    return await client().post("/api/auth/api-keys/", json={"name": name})


@mcp.tool()
async def delete_api_key(key_id: str) -> Any:
    """[admin] Revoca/elimina una API key por su id (UUID)."""
    return await client().delete(f"/api/auth/api-keys/{key_id}/", expect="none")


# ===========================================================================
# GRUPOS (listas de suscriptores)
# ===========================================================================

@mcp.tool()
async def list_groups() -> Any:
    """Lista los grupos de suscriptores (SubscriberList)."""
    return _as_listing(await client().get("/api/subscribers/groups/"))


@mcp.tool()
async def create_group(name: str, description: str | None = None) -> Any:
    """Crea un grupo de suscriptores."""
    return await client().post(
        "/api/subscribers/groups/", json=_clean({"name": name, "description": description})
    )


@mcp.tool()
async def update_group(group_id: int, name: str | None = None, description: str | None = None) -> Any:
    """Renombra o edita la descripción de un grupo."""
    return await client().patch(
        f"/api/subscribers/groups/{group_id}/",
        json=_clean({"name": name, "description": description}),
    )


@mcp.tool()
async def delete_group(group_id: int) -> Any:
    """Elimina un grupo y sus suscriptores (cascade). Debe quedar al menos un grupo."""
    return await client().delete(f"/api/subscribers/groups/{group_id}/", expect="none")


# ===========================================================================
# SUSCRIPTORES
# ===========================================================================

@mcp.tool()
async def list_subscribers(
    group_id: int | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> Any:
    """Lista suscriptores paginados. Sin `group_id` agrega TODOS los grupos.

    Filtra por email/nombre con `search`. `page_size` máx. 200. Devuelve
    count total, sendable_count (a quién le llegaría una campaña) y results.
    """
    params = _clean({
        "list": group_id,
        "search": search,
        "page": page,
        "page_size": page_size,
    })
    return await client().get("/api/subscribers/all/", params=params)


@mcp.tool()
async def add_subscriber(
    email: str,
    first_name: str | None = None,
    last_name: str | None = None,
    group_id: int | None = None,
) -> Any:
    """Añade (o recupera) un suscriptor. Sin `group_id` usa el grupo por defecto."""
    payload = _clean({
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "list": group_id,
    })
    return await client().post("/api/subscribers/add/", json=payload)


@mcp.tool()
async def update_subscriber(
    subscriber_id: str,
    email: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    status: str | None = None,
) -> Any:
    """Edita un suscriptor por id (UUID). `status`: active | unsubscribed | bounced."""
    payload = _clean({
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "status": status,
    })
    return await client().post(f"/api/subscribers/{subscriber_id}/", json=payload)


@mcp.tool()
async def delete_subscriber(subscriber_id: str) -> Any:
    """Elimina un suscriptor por id (UUID)."""
    return await client().delete(f"/api/subscribers/{subscriber_id}/", expect="none")


@mcp.tool()
async def bulk_delete_subscribers(ids: list[str]) -> Any:
    """Elimina hasta 500 suscriptores por lista de ids (UUID)."""
    return await client().post("/api/subscribers/bulk-delete/", json={"ids": ids})


@mcp.tool()
async def move_subscribers(ids: list[str], target_group_id: int) -> Any:
    """Mueve hasta 500 suscriptores (por ids) al grupo `target_group_id`.
    Omite los que ya existan en el grupo destino (unique por email)."""
    return await client().post(
        "/api/subscribers/move/", json={"ids": ids, "target_list": target_group_id}
    )


@mcp.tool()
async def import_subscribers(
    group_id: int | None = None,
    csv_data: str | None = None,
    file_path: str | None = None,
) -> Any:
    """Importa suscriptores desde CSV/TXT (uno por línea o con cabeceras). Pasa el
    contenido en `csv_data` o una ruta local en `file_path`. Detecta la columna
    de email por alias o auto-detección; ignora duplicados. Devuelve imported/skipped."""
    if not csv_data and file_path:
        csv_data = Path(file_path).expanduser().read_text(encoding="utf-8-sig")
    if not csv_data:
        raise MailerUpError("Indica csv_data o file_path.")
    payload = _clean({"list": group_id, "csv_data": csv_data})
    return await client().post("/api/subscribers/import/", json=payload)


@mcp.tool()
async def export_subscribers(
    group_id: int | None = None,
    file_path: str | None = None,
) -> Any:
    """Exporta suscriptores a CSV. Sin `group_id` exporta todos los grupos.

    Si das `file_path`, guarda el CSV ahí y devuelve la ruta; si no, devuelve el
    CSV como texto."""
    params = _clean({"list": group_id})
    csv_text = await client().get("/api/subscribers/export/", params=params, expect="text")
    if file_path:
        dest = Path(file_path).expanduser()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(csv_text, encoding="utf-8")
        return {"saved_to": str(dest), "bytes": len(csv_text.encode("utf-8"))}
    return csv_text


@mcp.tool()
async def low_engagement_subscribers(threshold: int = 25) -> Any:
    """Suscriptores activos con tasa de apertura por debajo de `threshold`%
    (solo quienes recibieron ≥1 campaña). Útil para limpiar la lista."""
    return _as_listing(await client().get(
        "/api/subscribers/low-engagement/", params={"threshold": threshold}
    ))


# ===========================================================================
# CAMPAÑAS
# ===========================================================================

@mcp.tool()
async def list_campaigns() -> Any:
    """Lista TODAS las campañas (con estado y stats resumidas)."""
    return _as_listing(await _collect("/api/campaigns/"))


@mcp.tool()
async def get_campaign(campaign_id: str) -> Any:
    """Devuelve una campaña completa (incluye html_content) por id (UUID)."""
    return await client().get(f"/api/campaigns/{campaign_id}/")


@mcp.tool()
async def preview_campaign(campaign_id: str) -> Any:
    """Devuelve el HTML del correo TAL CUAL lo reciben los suscriptores:
    personalizado con un destinatario de ejemplo, con pie de baja y enlaces
    reescritos (mismo render que el envío real). Útil para revisar el correo
    antes de enviarlo o para inspeccionar uno ya enviado."""
    return await client().get(f"/api/campaigns/{campaign_id}/preview/")


@mcp.tool()
async def create_campaign(
    name: str,
    subject: str,
    html_content: str,
    from_name: str | None = None,
    from_email: str | None = None,
    reply_to: str | None = None,
    preview_text: str | None = None,
    plain_content: str | None = None,
    group_id: int | None = None,
    send_to_all: bool | None = None,
    ab_enabled: bool | None = None,
    subject_b: str | None = None,
    ab_split_percent: int | None = None,
) -> Any:
    """Crea una campaña en estado borrador.

    Destinatarios: pon `group_id` (un grupo) o `send_to_all=True` (todos los
    grupos, deduplicando por email). A/B: `ab_enabled` + `subject_b` +
    `ab_split_percent`. El envío no ocurre aquí: usa send_campaign/schedule_campaign.
    """
    payload = _clean({
        "name": name,
        "subject": subject,
        "html_content": html_content,
        "from_name": from_name,
        "from_email": from_email,
        "reply_to": reply_to,
        "preview_text": preview_text,
        "plain_content": plain_content,
        "subscriber_list": group_id,
        "send_to_all": send_to_all,
        "ab_enabled": ab_enabled,
        "subject_b": subject_b,
        "ab_split_percent": ab_split_percent,
    })
    return await client().post("/api/campaigns/", json=payload)


@mcp.tool()
async def update_campaign(
    campaign_id: str,
    name: str | None = None,
    subject: str | None = None,
    html_content: str | None = None,
    from_name: str | None = None,
    from_email: str | None = None,
    reply_to: str | None = None,
    preview_text: str | None = None,
    plain_content: str | None = None,
    group_id: int | None = None,
    send_to_all: bool | None = None,
    ab_enabled: bool | None = None,
    subject_b: str | None = None,
    ab_split_percent: int | None = None,
) -> Any:
    """Edita una campaña (PATCH). Solo se envían los campos indicados."""
    payload = _clean({
        "name": name,
        "subject": subject,
        "html_content": html_content,
        "from_name": from_name,
        "from_email": from_email,
        "reply_to": reply_to,
        "preview_text": preview_text,
        "plain_content": plain_content,
        "subscriber_list": group_id,
        "send_to_all": send_to_all,
        "ab_enabled": ab_enabled,
        "subject_b": subject_b,
        "ab_split_percent": ab_split_percent,
    })
    return await client().patch(f"/api/campaigns/{campaign_id}/", json=payload)


@mcp.tool()
async def delete_campaign(campaign_id: str) -> Any:
    """Elimina una campaña por id (UUID)."""
    return await client().delete(f"/api/campaigns/{campaign_id}/", expect="none")


@mcp.tool()
async def send_campaign(campaign_id: str) -> Any:
    """Inicia el envío INMEDIATO de una campaña (borrador/programada/fallida).

    No bloquea: la marca 'sending' y el scheduler la entrega por lotes al ritmo
    configurado (send_rate_per_hour). Reintenta destinatarios fallidos sin
    reenviar a los ya entregados."""
    return await client().post(f"/api/campaigns/{campaign_id}/send/")


@mcp.tool()
async def schedule_campaign(campaign_id: str, scheduled_at: str) -> Any:
    """Programa una campaña para una fecha futura. `scheduled_at` en ISO 8601
    (p.ej. '2026-08-10T09:00:00+02:00'). Debe ser futura."""
    return await client().post(
        f"/api/campaigns/{campaign_id}/schedule/", json={"scheduled_at": scheduled_at}
    )


@mcp.tool()
async def unschedule_campaign(campaign_id: str) -> Any:
    """Cancela la programación de una campaña y la vuelve a borrador."""
    return await client().post(f"/api/campaigns/{campaign_id}/unschedule/")


@mcp.tool()
async def pause_campaign(campaign_id: str) -> Any:
    """Pausa una campaña que se está enviando (el scheduler deja de enviarla)."""
    return await client().post(f"/api/campaigns/{campaign_id}/pause/")


@mcp.tool()
async def resume_campaign(campaign_id: str) -> Any:
    """Reanuda una campaña pausada; continúa con los pendientes sin reenviar."""
    return await client().post(f"/api/campaigns/{campaign_id}/resume/")


@mcp.tool()
async def send_test_campaign(campaign_id: str, email: str) -> Any:
    """Envía un correo de PRUEBA de la campaña a `email` (no cuenta como envío real)."""
    return await client().post(
        f"/api/campaigns/{campaign_id}/send_test/", json={"email": email}
    )


@mcp.tool()
async def duplicate_campaign(campaign_id: str) -> Any:
    """Duplica una campaña como nuevo borrador ('(copia)')."""
    return await client().post(f"/api/campaigns/{campaign_id}/duplicate/")


@mcp.tool()
async def add_campaign_exclusions(
    campaign_id: str,
    emails: list[str] | None = None,
    csv_data: str | None = None,
    file_path: str | None = None,
) -> Any:
    """Añade emails a la lista de EXCLUSIÓN de una campaña (no recibirán el envío).

    Acepta `emails` (lista), `csv_data` (texto CSV/TXT) o `file_path` (ruta local)."""
    if not csv_data and file_path:
        csv_data = Path(file_path).expanduser().read_text(encoding="utf-8")
    if not csv_data and emails:
        csv_data = "\n".join(emails)
    if not csv_data:
        raise MailerUpError("Indica emails, csv_data o file_path.")
    return await client().post(
        f"/api/campaigns/{campaign_id}/exclude/", json={"csv_data": csv_data}
    )


@mcp.tool()
async def clear_campaign_exclusions(campaign_id: str) -> Any:
    """Vacía la lista de exclusión de una campaña."""
    return await client().delete(f"/api/campaigns/{campaign_id}/exclude/")


# ===========================================================================
# RECURSOS / ALMACENAMIENTO
# ===========================================================================

@mcp.tool()
async def list_resources() -> Any:
    """Lista TODOS los ficheros subidos (adjuntos/imágenes) con su URL pública."""
    return _as_listing(await _collect("/api/campaigns/resources/"))


@mcp.tool()
async def upload_resource(file_path: str) -> Any:
    """Sube un fichero (máx 25 MB) y devuelve su URL pública (/recurso/<nombre>).

    Se bloquean extensiones ejecutables/renderizables (.svg .html .js .php…)."""
    path = Path(file_path).expanduser()
    if not path.is_file():
        raise MailerUpError(f"No existe el fichero: {path}")
    content = path.read_bytes()
    files = {"file": (path.name, content, "application/octet-stream")}
    return await client().post("/api/campaigns/resources/", files=files)


@mcp.tool()
async def delete_resource(resource_id: str) -> Any:
    """Elimina un recurso subido por id (UUID)."""
    return await client().delete(f"/api/campaigns/resources/{resource_id}/", expect="none")


@mcp.tool()
async def storage_usage() -> Any:
    """Uso de disco del servidor y bytes ocupados por los recursos."""
    return await client().get("/api/campaigns/resources/disk-usage/")


# ===========================================================================
# FORMULARIOS
# ===========================================================================

@mcp.tool()
async def list_forms() -> Any:
    """Lista TODOS los formularios de suscripción."""
    return _as_listing(await _collect("/api/forms/"))


@mcp.tool()
async def get_form(form_id: str) -> Any:
    """Devuelve un formulario por id (UUID)."""
    return await client().get(f"/api/forms/{form_id}/")


@mcp.tool()
async def create_form(
    name: str,
    title: str | None = None,
    description: str | None = None,
    button_text: str | None = None,
    success_message: str | None = None,
    redirect_url: str | None = None,
    primary_color: str | None = None,
    collect_first_name: bool | None = None,
    collect_last_name: bool | None = None,
    target_group_id: int | None = None,
    is_active: bool | None = None,
) -> Any:
    """Crea un formulario público de suscripción (doble opt-in).

    `primary_color` en hex (#rrggbb). `target_group_id` = grupo destino de los
    nuevos suscriptores (si se omite, el grupo por defecto)."""
    payload = _clean({
        "name": name,
        "title": title,
        "description": description,
        "button_text": button_text,
        "success_message": success_message,
        "redirect_url": redirect_url,
        "primary_color": primary_color,
        "collect_first_name": collect_first_name,
        "collect_last_name": collect_last_name,
        "target_list": target_group_id,
        "is_active": is_active,
    })
    return await client().post("/api/forms/", json=payload)


@mcp.tool()
async def update_form(
    form_id: str,
    name: str | None = None,
    title: str | None = None,
    description: str | None = None,
    button_text: str | None = None,
    success_message: str | None = None,
    redirect_url: str | None = None,
    primary_color: str | None = None,
    collect_first_name: bool | None = None,
    collect_last_name: bool | None = None,
    target_group_id: int | None = None,
    is_active: bool | None = None,
) -> Any:
    """Edita un formulario (PATCH)."""
    payload = _clean({
        "name": name,
        "title": title,
        "description": description,
        "button_text": button_text,
        "success_message": success_message,
        "redirect_url": redirect_url,
        "primary_color": primary_color,
        "collect_first_name": collect_first_name,
        "collect_last_name": collect_last_name,
        "target_list": target_group_id,
        "is_active": is_active,
    })
    return await client().patch(f"/api/forms/{form_id}/", json=payload)


@mcp.tool()
async def delete_form(form_id: str) -> Any:
    """Elimina un formulario por id (UUID)."""
    return await client().delete(f"/api/forms/{form_id}/", expect="none")


@mcp.tool()
async def get_form_embed(form_id: str) -> Any:
    """Devuelve el snippet HTML embebible del formulario y su URL pública."""
    return await client().get(f"/api/forms/{form_id}/embed/")


# ===========================================================================
# AUTOMATIZACIONES
# ===========================================================================

@mcp.tool()
async def list_automations() -> Any:
    """Lista TODAS las automatizaciones (con sus pasos y contadores de matriculados)."""
    return _as_listing(await _collect("/api/automations/"))


@mcp.tool()
async def get_automation(automation_id: str) -> Any:
    """Devuelve una automatización por id (UUID), con sus pasos."""
    return await client().get(f"/api/automations/{automation_id}/")


@mcp.tool()
async def create_automation(
    name: str, form_id: str | None = None, is_active: bool | None = None
) -> Any:
    """Crea una automatización (secuencia de emails). Puedes vincularla a un
    formulario con `form_id` (relación 1-a-1: cada formulario, una automatización)."""
    payload = _clean({"name": name, "form": form_id, "is_active": is_active})
    return await client().post("/api/automations/", json=payload)


@mcp.tool()
async def update_automation(
    automation_id: str,
    name: str | None = None,
    form_id: str | None = None,
    is_active: bool | None = None,
) -> Any:
    """Edita una automatización (nombre, formulario vinculado, activa/inactiva)."""
    payload = _clean({"name": name, "form": form_id, "is_active": is_active})
    return await client().patch(f"/api/automations/{automation_id}/", json=payload)


@mcp.tool()
async def delete_automation(automation_id: str) -> Any:
    """Elimina una automatización por id (UUID)."""
    return await client().delete(f"/api/automations/{automation_id}/", expect="none")


@mcp.tool()
async def add_automation_step(
    automation_id: str,
    subject: str,
    html_content: str,
    delay_amount: int,
    delay_unit: str = "days",
    from_name: str | None = None,
    from_email: str | None = None,
    order: int | None = None,
) -> Any:
    """Añade un paso (correo) a una automatización.

    `delay_unit`: minutes | hours | days — retraso desde la suscripción/paso previo.
    Si no indicas `order`, se añade al final."""
    payload = _clean({
        "subject": subject,
        "html_content": html_content,
        "delay_amount": delay_amount,
        "delay_unit": delay_unit,
        "from_name": from_name,
        "from_email": from_email,
        "order": order,
    })
    return await client().post(f"/api/automations/{automation_id}/steps/", json=payload)


@mcp.tool()
async def update_automation_step(
    automation_id: str,
    step_id: str,
    subject: str | None = None,
    html_content: str | None = None,
    delay_amount: int | None = None,
    delay_unit: str | None = None,
    from_name: str | None = None,
    from_email: str | None = None,
    order: int | None = None,
) -> Any:
    """Edita un paso de una automatización (PATCH)."""
    payload = _clean({
        "subject": subject,
        "html_content": html_content,
        "delay_amount": delay_amount,
        "delay_unit": delay_unit,
        "from_name": from_name,
        "from_email": from_email,
        "order": order,
    })
    return await client().patch(
        f"/api/automations/{automation_id}/steps/{step_id}/", json=payload
    )


@mcp.tool()
async def delete_automation_step(automation_id: str, step_id: str) -> Any:
    """Elimina un paso de una automatización por su id (UUID)."""
    return await client().delete(
        f"/api/automations/{automation_id}/steps/{step_id}/", expect="none"
    )


# ===========================================================================
# ANALÍTICAS Y ENTREGABILIDAD
# ===========================================================================

@mcp.tool()
async def analytics_overview() -> Any:
    """KPIs globales: suscriptores, campañas, envíos, aperturas/clics medios y
    desglose por campaña enviada."""
    return await client().get("/api/analytics/overview/")


@mcp.tool()
async def campaign_analytics(campaign_id: str) -> Any:
    """Analítica detallada de una campaña: tasas, destinatarios (hasta 500),
    top enlaces y, si aplica, stats A/B."""
    return await client().get(f"/api/analytics/campaign/{campaign_id}/")


_CAMPAIGN_METRICS = {
    "open_rate", "click_rate", "click_through_open_rate",
    "opens", "clicks", "delivered", "sends",
    "unsubscribe_rate", "bounce_rate", "unsubscribes",
}


@mcp.tool()
async def top_campaigns(
    metric: str = "open_rate", limit: int = 10, order: str = "desc"
) -> Any:
    """Ranking de campañas ENVIADAS por una métrica — para saber qué correos
    rindieron mejor (o peor).

    `metric`: open_rate | click_rate | click_through_open_rate | opens | clicks |
    delivered | sends | unsubscribe_rate | bounce_rate | unsubscribes.
    `order`: desc (mejores primero, por defecto) | asc.
    Devuelve las campañas ordenadas con sus métricas clave y los promedios
    globales de referencia. Para el detalle completo de una campaña (destinatarios,
    top enlaces, A/B) usa `campaign_analytics`.
    """
    if metric not in _CAMPAIGN_METRICS:
        raise MailerUpError(
            f"metric inválida: {metric}. Válidas: {', '.join(sorted(_CAMPAIGN_METRICS))}."
        )
    data = await client().get("/api/analytics/overview/")
    campaigns = data.get("campaigns", []) if isinstance(data, dict) else []
    reverse = order != "asc"
    ranked = sorted(campaigns, key=lambda c: (c.get(metric) or 0), reverse=reverse)
    keys = (
        "id", "name", "subject", "sent_at", "sends", "delivered", "opens",
        "clicks", "open_rate", "click_rate", "click_through_open_rate",
        "unsubscribe_rate", "bounce_rate",
    )
    items = [{k: c.get(k) for k in keys} for c in ranked[: max(1, limit)]]
    return {
        "metric": metric,
        "order": order,
        "count": len(items),
        "items": items,
        "global": {
            k: data.get(k)
            for k in ("avg_open_rate", "avg_click_rate", "total_delivered",
                      "total_opens", "total_clicks", "sent_campaigns")
        },
    }


@mcp.tool()
async def automations_overview() -> Any:
    """KPIs globales de automatizaciones y desglose por automatización."""
    return await client().get("/api/analytics/automations/overview/")


@mcp.tool()
async def automation_analytics(automation_id: str) -> Any:
    """Analítica de una automatización, con métricas por paso."""
    return await client().get(f"/api/analytics/automation/{automation_id}/")


@mcp.tool()
async def subscriptions_timeseries(period: str = "day") -> Any:
    """Serie temporal de altas y bajas. `period`: day | week | month."""
    return await client().get(
        "/api/analytics/subscriptions/timeseries/", params={"period": period}
    )


@mcp.tool()
async def deliverability() -> Any:
    """Entregabilidad: tasa de éxito/error de envíos, motivos de error, rebotes,
    campañas en curso (progreso/ETA) y campañas enviadas."""
    return await client().get("/api/analytics/deliverability/")


@mcp.tool()
async def deliverability_recipients(
    campaign_id: str, filter: str = "received", q: str | None = None
) -> Any:
    """Destinatarios de una campaña por categoría. `filter`: received | pending | error.
    `q` busca por email/nombre. Máx 500 filas (los contadores son el total real)."""
    params = _clean({"filter": filter, "q": q})
    return await client().get(
        f"/api/analytics/deliverability/campaign/{campaign_id}/recipients/", params=params
    )


@mcp.tool()
async def retry_failed_sends() -> Any:
    """Re-encola TODOS los envíos fallidos (los que dieron error) para reintentarlos
    al ritmo configurado, sin reenviar a quienes sí recibieron el correo."""
    return await client().post("/api/analytics/retry-failed/")


# ===========================================================================
# BACKUPS
# ===========================================================================

@mcp.tool()
async def backup_all(dest_dir: str | None = None) -> Any:
    """Backup lógico COMPLETO vía API (funciona con SQLite o PostgreSQL).

    Vuelca a una carpeta local (por defecto MAILERUP_BACKUP_DIR o
    ~/mailerup-backups/backup_<fecha>/): perfil, grupos, TODOS los suscriptores
    por grupo (CSV + JSON), campañas completas (incl. HTML), automatizaciones,
    formularios y las analíticas. Devuelve un resumen con rutas y contadores.

    Es restaurable: los CSV se reimportan con import_subscribers y el resto queda
    documentado en JSON. Para un backup binario de la BD usa
    export_database_sqlite (solo SQLite) o pg_dump en el servidor (PostgreSQL).
    """
    c = client()
    base = Path(dest_dir).expanduser() if dest_dir else _backup_dir()
    out = base / f"backup_{_stamp()}"
    (out / "subscribers").mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {"created_at": datetime.now(timezone.utc).isoformat(), "files": []}

    def _write_json(name: str, data: Any) -> None:
        p = out / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        manifest["files"].append(str(p.relative_to(out)))

    # Perfil (sin secretos)
    _write_json("account.json", await c.get("/api/auth/me/"))

    # Grupos + suscriptores por grupo
    groups = await c.get("/api/subscribers/groups/")
    _write_json("groups.json", groups)
    counts: dict[str, int] = {}
    for g in groups if isinstance(groups, list) else []:
        gid = g.get("id")
        # CSV (formato importable)
        csv_text = await c.get(
            "/api/subscribers/export/", params={"list": gid}, expect="text"
        )
        csv_path = out / "subscribers" / f"group_{gid}.csv"
        csv_path.write_text(csv_text, encoding="utf-8")
        manifest["files"].append(str(csv_path.relative_to(out)))
        # Recuento
        first = await c.get(
            "/api/subscribers/all/", params={"list": gid, "page": 1, "page_size": 1}
        )
        counts[str(gid)] = first.get("count", 0)

    # Campañas completas (la lista viene paginada: recolectamos todas)
    camp_list = await _collect("/api/campaigns/")
    full_campaigns = []
    for item in camp_list if isinstance(camp_list, list) else []:
        full_campaigns.append(await c.get(f"/api/campaigns/{item['id']}/"))
    _write_json("campaigns.json", full_campaigns)

    # Automatizaciones (la lista ya trae los pasos)
    _write_json("automations.json", await _collect("/api/automations/"))

    # Formularios
    _write_json("forms.json", await _collect("/api/forms/"))

    # Recursos (metadatos)
    _write_json("resources.json", await _collect("/api/campaigns/resources/"))

    # Analíticas (snapshot)
    _write_json("analytics_overview.json", await c.get("/api/analytics/overview/"))
    _write_json("automations_overview.json", await c.get("/api/analytics/automations/overview/"))
    _write_json("deliverability.json", await c.get("/api/analytics/deliverability/"))

    manifest["subscriber_counts"] = counts
    manifest["totals"] = {
        "groups": len(groups) if isinstance(groups, list) else 0,
        "subscribers": sum(counts.values()),
        "campaigns": len(full_campaigns),
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return {"backup_dir": str(out), **manifest["totals"], "files": manifest["files"]}


@mcp.tool()
async def export_database_sqlite(file_path: str | None = None) -> Any:
    """Descarga la BD SQLite completa (GET /api/auth/db-export/, solo admin).

    ⚠️ Solo funciona si el servidor usa SQLite (desarrollo). En producción con
    PostgreSQL este endpoint devuelve 404; usa `backup_all` para un backup lógico
    vía API, o ejecuta `pg_dump` en el servidor para un volcado binario completo.
    """
    data = await client().get("/api/auth/db-export/", expect="bytes")
    dest = Path(file_path).expanduser() if file_path else _backup_dir() / f"mailerup_{_stamp()}.sqlite3"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return {"saved_to": str(dest), "bytes": len(data)}


# ===========================================================================
# ESCAPE HATCH
# ===========================================================================

@mcp.tool()
async def api_request(
    method: str,
    path: str,
    json_body: dict | None = None,
    params: dict | None = None,
) -> Any:
    """Petición cruda a la API para lo que no cubran las demás herramientas.

    `method`: GET/POST/PATCH/PUT/DELETE. `path`: ruta que empieza por /api/…
    Usa la misma sesión autenticada (cookie JWT). Devuelve el JSON de respuesta."""
    return await client().request(
        method.upper(), path, json=json_body, params=params
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
