"""Cliente HTTP para la API REST de MailerUp.

MailerUp autentica la API privada **exclusivamente por cookie JWT**
(`apps.accounts.authentication.CookieJWTAuthentication`): no acepta
`Authorization: Bearer` en los endpoints privados. Por eso este cliente:

1. Hace login en ``POST /api/auth/token/`` con usuario/contraseña, lo que fija
   las cookies HttpOnly ``access`` (15 min) y ``refresh`` (7 días).
2. Reutiliza el *cookie jar* de ``httpx.AsyncClient`` en cada petición.
3. Ante un 401, refresca con ``POST /api/auth/token/refresh/`` (rota el refresh)
   y reintenta una vez; si el refresh falla, vuelve a hacer login.

Las vistas DRF son ``csrf_exempt``, así que las peticiones con cookie no
necesitan token CSRF (igual que hace el SPA de React).
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx


class MailerUpError(RuntimeError):
    """Error de la API de MailerUp con contexto legible (status + cuerpo)."""

    def __init__(self, message: str, *, status: int | None = None, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on", "si", "sí")


class MailerUpClient:
    """Cliente asíncrono con login perezoso y refresco automático de token."""

    def __init__(
        self,
        base_url: str | None = None,
        email: str | None = None,
        password: str | None = None,
        *,
        verify_ssl: bool | None = None,
        timeout: float | None = None,
    ):
        self.base_url = (base_url or os.environ.get("MAILERUP_BASE_URL", "")).rstrip("/")
        # El modelo User de MailerUp usa USERNAME_FIELD="email": el login es por
        # email. Aceptamos MAILERUP_EMAIL (preferido) o MAILERUP_USERNAME (alias).
        self.email = (
            email
            or os.environ.get("MAILERUP_EMAIL")
            or os.environ.get("MAILERUP_USERNAME", "")
        )
        self.password = password or os.environ.get("MAILERUP_PASSWORD", "")
        if verify_ssl is None:
            verify_ssl = _env_bool("MAILERUP_VERIFY_SSL", True)
        if timeout is None:
            timeout = float(os.environ.get("MAILERUP_TIMEOUT", "120"))

        if not self.base_url:
            raise MailerUpError(
                "Falta MAILERUP_BASE_URL (p.ej. https://newsletter.example.com)."
            )

        self._verify = verify_ssl
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._auth_lock = asyncio.Lock()
        self._logged_in = False

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                verify=self._verify,
                timeout=self._timeout,
                follow_redirects=True,
                headers={"User-Agent": "mailerup-mcp/1.0"},
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            self._logged_in = False

    # -- Autenticación -------------------------------------------------------

    async def _login(self) -> None:
        if not self.email or not self.password:
            raise MailerUpError(
                "Faltan credenciales: define MAILERUP_EMAIL y MAILERUP_PASSWORD."
            )
        client = await self._ensure_client()
        resp = await client.post(
            "/api/auth/token/",
            json={"email": self.email, "password": self.password},
        )
        if resp.status_code != 200:
            raise MailerUpError(
                "Login fallido: revisa MAILERUP_EMAIL/MAILERUP_PASSWORD y "
                f"MAILERUP_BASE_URL. (HTTP {resp.status_code})",
                status=resp.status_code,
                body=_safe_body(resp),
            )
        self._logged_in = True

    async def _refresh(self) -> bool:
        client = await self._ensure_client()
        resp = await client.post("/api/auth/token/refresh/")
        if resp.status_code == 200:
            self._logged_in = True
            return True
        return False

    async def _authenticate(self) -> None:
        async with self._auth_lock:
            if not self._logged_in:
                await self._login()

    # -- Petición genérica con reintento tras 401 ----------------------------

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict | None = None,
        data: dict | None = None,
        files: dict | None = None,
        expect: str = "json",
    ) -> Any:
        """Ejecuta una petición autenticada.

        ``expect``: "json" (default) devuelve el JSON parseado; "bytes" devuelve
        el contenido binario; "text" el texto; "none" no devuelve cuerpo (204).
        """
        await self._authenticate()
        client = await self._ensure_client()

        async def _do() -> httpx.Response:
            return await client.request(
                method, path, json=json, params=params, data=data, files=files
            )

        resp = await _do()

        if resp.status_code == 401:
            # Token de acceso caducado: intenta refrescar y, si no, re-loguea.
            async with self._auth_lock:
                refreshed = await self._refresh()
                if not refreshed:
                    self._logged_in = False
                    await self._login()
            resp = await _do()

        if resp.status_code >= 400:
            body = _safe_body(resp)
            raise MailerUpError(
                f"{method} {path} → HTTP {resp.status_code}: {_detail(body)}",
                status=resp.status_code,
                body=body,
            )

        if expect == "bytes":
            return resp.content
        if expect == "text":
            return resp.text
        if expect == "none" or resp.status_code == 204 or not resp.content:
            return {"ok": True, "status": resp.status_code}
        try:
            return resp.json()
        except ValueError:
            return resp.text

    # Atajos ---------------------------------------------------------------
    async def get(self, path: str, **kw) -> Any:
        return await self.request("GET", path, **kw)

    async def post(self, path: str, **kw) -> Any:
        return await self.request("POST", path, **kw)

    async def patch(self, path: str, **kw) -> Any:
        return await self.request("PATCH", path, **kw)

    async def put(self, path: str, **kw) -> Any:
        return await self.request("PUT", path, **kw)

    async def delete(self, path: str, **kw) -> Any:
        return await self.request("DELETE", path, **kw)


def _safe_body(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        text = resp.text or ""
        return text[:1000]


def _detail(body: Any) -> str:
    """Extrae un mensaje legible del cuerpo de error de DRF."""
    if isinstance(body, dict):
        if "detail" in body:
            return str(body["detail"])
        # Errores de validación por campo: {"campo": ["msg", ...]}
        parts = []
        for field, msgs in body.items():
            if isinstance(msgs, (list, tuple)):
                parts.append(f"{field}: {'; '.join(str(m) for m in msgs)}")
            else:
                parts.append(f"{field}: {msgs}")
        return " | ".join(parts) if parts else str(body)
    return str(body)[:300]
