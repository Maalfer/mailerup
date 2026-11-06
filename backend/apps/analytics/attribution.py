"""Normalización y clasificación del origen de un lead (first-touch).

El navegador (static/js/lead-tracking.js de la web) envía utm_*, los IDs de ManyChat y un
visitor_id junto al formulario; aquí se sanea y se decide `source`. Ver docs/TRAZABILIDAD.md.
"""
import re
from urllib.parse import urlparse

_CTRL = re.compile(r"[\x00-\x1f\x7f]")
_FIELDS = {"utm_source": 100, "utm_medium": 100, "utm_campaign": 100, "utm_content": 100,
           "manychat_sid": 40, "manychat_pid": 40, "visitor_id": 40}
_SOCIAL = {"instagram": "instagram", "facebook": "facebook", "youtube": "youtube", "t.co": "twitter",
           "twitter": "twitter", "x.com": "twitter", "tiktok": "tiktok", "google": "google",
           "linkedin": "linkedin", "skool": "skool", "dockerlabs": "dockerlabs"}

# Apps/webmails que abren el enlace en su propio navegador: su referrer NO es una búsqueda ni una red
# social (p. ej. "com.google.android.gm" es la app de Gmail en Android, no google.com/search). Sin esto,
# quien abre un correo nuestro desde el móvil contaba como tráfico "orgánico de Google".
_EMAIL_CLIENTS = ("android.gm", "mail.google.com", "outlook.live.com", "outlook.office", "mail.yahoo.com",
                  "ymail.com", "mail.ru", "webmail")


# Alias habituales de utm_source -> nombre canónico, para que un mismo canal no salga repartido en el informe.
_ALIASES = {"ig": "instagram", "insta": "instagram", "l.instagram.com": "instagram", "fb": "facebook", "yt": "youtube",
            "tt": "tiktok", "x": "twitter", "tw": "twitter"}


def canonical_source(name):
    n = (name or "").strip().lower()
    return _ALIASES.get(n, n)


def _clean(value, limit):
    return _CTRL.sub("", str(value or "")).strip()[:limit]


def host_of(url):
    try:
        return (urlparse(url or "").hostname or "")[:100].lower()
    except Exception:
        return ""


def path_of(url):
    try:
        return (urlparse(url or "").path or "")[:200]
    except Exception:
        return ""


def clean_attribution(data, referer=""):
    """`data`: dict/QueryDict con los campos del formulario. Devuelve los campos saneados + source."""
    out = {k: _clean(data.get(k), n) for k, n in _FIELDS.items()}
    out["referrer_host"] = _clean(data.get("referrer_host") or host_of(data.get("ref") or referer), 100).lower()
    out["landing_path"] = _clean(data.get("landing") or path_of(referer), 200)
    out["source"] = derive_source(out)
    return out


def derive_source(a):
    """manychat > utm_source explícito > cliente de correo (clic dentro de un email) > red social por
    referrer > web."""
    utm = canonical_source(a.get("utm_source"))
    ref = (a.get("referrer_host") or "").lower()
    if a.get("manychat_sid") or a.get("manychat_pid") or utm == "manychat" or "manychat" in ref:
        return "manychat"
    if utm:
        return "email" if utm in ("newsletter", "email") else utm[:30]
    if any(key in ref for key in _EMAIL_CLIENTS):
        return "email"
    for key, name in _SOCIAL.items():
        if key in ref:
            return name
    return "web" if ref or a.get("landing_path") else ""
