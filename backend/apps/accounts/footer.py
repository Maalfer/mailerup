"""Inyección del pie configurable (líneas reenviar/suscribirse) al ENVIAR.

Los correos cuyo pie se escribió a mano (no con el botón "Insertar pie" del
editor) no usan la configuración del usuario. Este helper inserta, en el momento
del envío, las líneas configurables `footer_forward_text` y `footer_subscribe_text`
justo antes del enlace de baja (`{{unsubscribe_url}}`), de forma idempotente
(no duplica si el texto ya está presente). Así la config "carga" dinámicamente
en campañas/automatizaciones existentes y futuras.
"""
import re

_URL_RE = re.compile(r"(?:https?://)?[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/[^\s<]*)?", re.IGNORECASE)


def _escape(s):
    # Las comillas también se escapan: _linkify interpola URLs detectadas
    # directamente en href="…", y su regex no excluye comillas del "path" —
    # sin esto, un footer_forward_text/footer_subscribe_text con una comilla
    # doble podría cerrar el atributo href e inyectar atributos HTML propios
    # (p. ej. onmouseover=) en el pie de TODOS los correos salientes.
    return (
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;").replace("'", "&#39;")
    )


def _linkify(text):
    def repl(m):
        u = m.group(0)
        href = u if u.lower().startswith(("http://", "https://")) else "https://" + u
        return f'<a href="{href}" style="color:inherit;text-decoration:none">{u}</a>'
    return _URL_RE.sub(repl, text)


def _line(text):
    return (
        '<p style="margin:0 0 8px;font-size:13px;line-height:1.6;color:#64748b">'
        f"▸ {_linkify(_escape(text))}</p>"
    )


def build_footer_html(user):
    """Genera el bloque de pie configurable completo (igual que el botón
    'Insertar pie con baja' del editor): empresa, dirección, líneas reenviar/
    suscribirse y la línea de baja discreta con el enlace {{unsubscribe_url}}."""
    company = _escape((getattr(user, "footer_company", "") or "").strip())
    address = _escape((getattr(user, "footer_address", "") or "").strip())
    text = _escape((getattr(user, "footer_unsubscribe_text", "") or "").strip()
                   or "Si ya no quieres recibir nuestros correos, puedes darte de baja en cualquier momento.")
    label = _escape((getattr(user, "footer_button_label", "") or "").strip() or "Darse de baja")
    fwd = (getattr(user, "footer_forward_text", "") or "").strip()
    sub = (getattr(user, "footer_subscribe_text", "") or "").strip()

    # Todo el pie en gris clarito (#94a3b8) y los enlaces sin subrayar (heredan
    # el color), para que no se noten.
    parts = [
        '<hr data-mailerup="footer-divider" style="border:none;border-top:1px solid #e2e8f0;margin:36px 0 0" />',
        '<div data-mailerup="footer" style="text-align:center;color:#94a3b8;font-size:13px;line-height:1.6;padding:16px 8px">',
    ]
    if company:
        parts.append(f'<div style="font-weight:600">{company}</div>')
    if address:
        parts.append(f"<div>{address}</div>")
    if fwd:
        parts.append(f'<div style="margin-top:10px">▸ {_linkify(_escape(fwd))}</div>')
    if sub:
        parts.append(f'<div style="margin-top:4px">▸ {_linkify(_escape(sub))}</div>')
    parts.append(
        '<div style="margin-top:18px;font-size:11px">'
        f'{text} <a href="{{{{unsubscribe_url}}}}" style="color:inherit;text-decoration:none">{label}</a>.</div>'
    )
    parts.append("</div>")
    return "".join(parts)


def strip_footer(html):
    """Elimina del HTML cualquier pie existente, dejando solo el cuerpo. Maneja:
    - el pie configurable (bloque data-mailerup, con o sin divisor);
    - el pie 'destrozado' por el editor TipTap (<hr> + <p><strong>empresa</strong>
      </p> + <p>▸ …</p> + <p>… {{unsubscribe_url}} …</p>);
    - una línea de baja suelta escrita a mano.
    Se usa antes de añadir un pie nuevo y limpio al enviar (evita duplicados)."""
    if not html:
        return html

    # 1) Pie configurable con marcador: cortar desde el divisor o el <div>.
    for marker in ('data-mailerup="footer-divider"', 'data-mailerup="footer"'):
        i = html.find(marker)
        if i != -1:
            cut = html.rfind("<hr", 0, i)
            if cut == -1:
                cut = html.rfind("<div", 0, i)
            if cut != -1:
                return html[:cut].rstrip()

    # 2) Pie sin marcador (TipTap o escrito a mano): localizar la línea de baja.
    i = html.find("{{unsubscribe_url}}")
    if i == -1:
        return html
    end = html.find("</p>", i)
    end = end + 4 if end != -1 else len(html)
    start = html.rfind("<p", 0, i)
    if start == -1:
        start = i
    # Comerse hacia atrás las líneas de pie (con ▸) y el <p><strong>empresa</strong></p>.
    while True:
        prev = html.rfind("<p", 0, start)
        if prev == -1:
            break
        seg = html[prev:start].lower()
        if "▸" in html[prev:start] or "<strong>" in seg:
            start = prev
            continue
        break
    # Y un <hr> inmediatamente anterior (el divisor del pie).
    m = re.search(r"<hr\b[^>]*>\s*$", html[:start])
    if m:
        start = m.start()
    return (html[:start] + html[end:]).rstrip()


_FULL_DOC_RE = re.compile(r"</body\s*>|</html\s*>", re.IGNORECASE)


def is_full_document(html):
    """True si el HTML es un documento completo (correo escrito en modo HTML con
    su propio <body>/</html>), no un fragmento del editor TipTap."""
    return bool(html) and bool(_FULL_DOC_RE.search(html))


def inject_before_body_end(html, snippet):
    """Inserta `snippet` justo antes de </body> (o </html> si no hay body). Si el
    HTML no es un documento completo, lo añade al final. Mantiene el HTML válido
    en correos escritos a mano en modo HTML: el pie y el pixel de seguimiento
    quedan DENTRO del documento, no flotando tras </html>."""
    if not snippet:
        return html
    html = html or ""
    for tag in ("</body>", "</html>"):
        idx = html.lower().rfind(tag)
        if idx != -1:
            return html[:idx] + snippet + html[idx:]
    return html + snippet


def apply_footer(html, user):
    """Quita cualquier pie del cuerpo y añade uno nuevo y limpio desde la config.
    Es lo que se usa AL ENVIAR para garantizar estilo correcto y sin duplicados,
    pase lo que pase con el editor.

    Para correos en **modo HTML** (documento completo) NO se aplica `strip_footer`
    —pensado para los fragmentos de TipTap, destrozaría la maqueta de tablas—:
    si el autor ya colocó su propio enlace de baja (`{{unsubscribe_url}}`) se
    respeta su diseño tal cual; si no, se inserta el pie configurable antes de
    `</body>` para garantizar la baja legal sin romper el documento."""
    html = html or ""
    if is_full_document(html):
        if "{{unsubscribe_url}}" in html:
            return html
        return inject_before_body_end(html, build_footer_html(user))
    return strip_footer(html) + build_footer_html(user)


def replace_handwritten_footer(html, user):
    """Sustituye el <p> que contiene {{unsubscribe_url}} (la línea de baja escrita
    a mano) por el pie configurable completo. Si ya hay un pie data-mailerup, no
    toca nada. Si no hay línea de baja, añade el pie al final. Devuelve el HTML
    modificado (o el original si no procede)."""
    if not html:
        return html
    if 'data-mailerup="footer"' in html:
        return html
    block = build_footer_html(user)
    idx = html.find("{{unsubscribe_url}}")
    if idx == -1:
        return html.rstrip() + block
    p_start = html.rfind("<p", 0, idx)
    p_end = html.find("</p>", idx)
    if p_start == -1 or p_end == -1:
        return html
    p_end += len("</p>")
    return html[:p_start] + block + html[p_end:]


def inject_config_footer(html, user):
    """Inserta las líneas configurables del pie antes de `{{unsubscribe_url}}`.

    Idempotente: si el texto de una línea ya aparece en el HTML (p. ej. el pie se
    insertó con el editor), no la duplica. Si no hay enlace de baja, las añade al
    final.
    """
    if not html or user is None:
        return html

    # Si ya hay un pie configurable completo (insertado por el editor o por el
    # backfill), no inyectar nada: ya incluye estas líneas (y la URL puede ir
    # enlazada, lo que rompería el dedup por substring de abajo).
    if 'data-mailerup="footer"' in html:
        return html

    lines = []
    fwd = (getattr(user, "footer_forward_text", "") or "").strip()
    sub = (getattr(user, "footer_subscribe_text", "") or "").strip()
    if fwd and fwd not in html:
        lines.append(_line(fwd))
    if sub and sub not in html:
        lines.append(_line(sub))
    if not lines:
        return html

    block = "".join(lines)
    idx = html.find("{{unsubscribe_url}}")
    if idx == -1:
        return html + block
    # Insertar antes del <p> (o, en su defecto, del enlace) que contiene la baja.
    p_start = html.rfind("<p", 0, idx)
    insert_at = p_start if p_start != -1 else idx
    return html[:insert_at] + block + html[insert_at:]
