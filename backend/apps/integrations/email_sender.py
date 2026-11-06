import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseEmailSender(ABC):
    @abstractmethod
    def send(self, to_email, to_name, from_name, from_email, subject, html,
             campaign_id=None, subscriber_id=None, list_unsubscribe_url=None) -> str:
        pass


def html_to_text(html: str) -> str:
    """Versión text/plain legible del HTML (enlaces como «texto (url)»).

    Un multipart/alternative con un texto real (en vez de «tu cliente no soporta
    HTML») mejora la entregabilidad: los filtros de spam penalizan los correos
    cuya parte de texto está vacía o es un relleno.
    """
    import re
    from html import unescape
    if not html:
        return ""
    t = re.sub(r"(?is)<(script|style|head)[^>]*>.*?</\1>", "", html)
    t = re.sub(r"(?is)<div[^>]*display:\s*none[^>]*>.*?</div>", "", t)  # preheader oculto
    t = re.sub(r'(?is)<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
               lambda m: (f"{re.sub(r'<[^>]+>', '', m.group(2)).strip()} ({m.group(1)})"
                          if not m.group(1).startswith(("#", "mailto:")) else re.sub(r'<[^>]+>', '', m.group(2))), t)
    t = re.sub(r"(?i)<br\s*/?>", "\n", t)
    t = re.sub(r"(?i)</(p|div|h[1-6]|li|tr|pre|table|blockquote)>", "\n\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = unescape(t)
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip() + "\n"


class EmailSendError(Exception):
    pass


class SMTPSender(BaseEmailSender):
    def __init__(self, host, port, user, password, use_tls=True, use_ssl=False):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.use_tls = use_tls
        self.use_ssl = use_ssl

    def send(self, to_email, to_name, from_name, from_email, subject, html,
             campaign_id=None, subscriber_id=None, list_unsubscribe_url=None):
        import smtplib
        import socket
        import ssl as ssl_mod
        from email.message import EmailMessage
        from email.utils import formataddr, make_msgid, formatdate

        if not self.host:
            raise EmailSendError("Falta el host SMTP en ajustes.")
        if not from_email and not self.user:
            raise EmailSendError("Falta el email del remitente.")

        # El servidor SMTP solo permite enviar como el usuario autenticado.
        # Si el From no coincide, Raiola/IONOS aceptan pero el receptor descarta por SPF.
        # Forzamos el From visible al smtp_user cuando hay desalineación de dominio.
        final_from = from_email or self.user
        if self.user and "@" in self.user and "@" in final_from:
            if final_from.split("@", 1)[1].lower() != self.user.split("@", 1)[1].lower():
                final_from = self.user

        msg = EmailMessage()
        msg["From"] = formataddr((from_name or "", final_from))
        msg["To"] = formataddr((to_name or "", to_email))
        msg["Subject"] = subject
        # Message-ID propio con el dominio del remitente. IMPRESCINDIBLE para DKIM
        # con Raiola: si el mensaje sale sin Message-ID, com1033 lo firma (lo
        # incluye en h=) pero el relay de salida (admin.relay.raiolanetworks.com)
        # le añade/reescribe uno DESPUÉS de firmar, rompiendo la firma. Fijándolo
        # aquí, com1033 firma este Message-ID y el relay ya no lo toca → DKIM pass.
        msg["Message-ID"] = make_msgid(domain=final_from.rsplit("@", 1)[-1])
        msg["Date"] = formatdate(localtime=True)
        # Cabeceras de baja en un clic (RFC 8058). Gmail/Yahoo las exigen a
        # remitentes masivos: muestran el botón "Cancelar suscripción" y, al
        # pulsarlo, hacen POST a la URL (sin abrir el correo). Reduce marcas de
        # spam y mejora la reputación de envío.
        if list_unsubscribe_url:
            msg["List-Unsubscribe"] = f"<{list_unsubscribe_url}>"
            msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
        # Feedback-ID (Google Postmaster): permite el bucle de retroalimentación
        # de spam por campaña. Formato campaña:tipo:origen:remitente; el último
        # campo (ID del remitente) debe ser constante para todo el tráfico.
        _fb_dom = final_from.rsplit("@", 1)[-1]
        msg["Feedback-ID"] = f"{campaign_id or 'automation'}:newsletter:mailerup:{_fb_dom}"
        msg.set_content(html_to_text(html) or "Abre este correo en un cliente con soporte HTML.")
        msg.add_alternative(html, subtype="html")

        try:
            if self.use_ssl:
                conn = smtplib.SMTP_SSL(self.host, self.port, timeout=20)
            else:
                conn = smtplib.SMTP(self.host, self.port, timeout=20)
        except (socket.gaierror, socket.timeout, ConnectionRefusedError, OSError) as exc:
            raise EmailSendError(
                f"No se pudo conectar a {self.host}:{self.port} ({exc.__class__.__name__}: {exc})"
            )

        try:
            conn.ehlo()
            if not self.use_ssl and self.use_tls:
                try:
                    conn.starttls()
                    conn.ehlo()
                except (smtplib.SMTPException, ssl_mod.SSLError) as exc:
                    raise EmailSendError(f"STARTTLS falló: {exc}")
            if self.user:
                try:
                    conn.login(self.user, self.password)
                except smtplib.SMTPAuthenticationError as exc:
                    raise EmailSendError(
                        f"Autenticación SMTP rechazada por {self.host} "
                        f"(código {exc.smtp_code}): {exc.smtp_error.decode(errors='ignore') if isinstance(exc.smtp_error, bytes) else exc.smtp_error}"
                    )
                except smtplib.SMTPException as exc:
                    raise EmailSendError(f"Error de login SMTP: {exc}")
            try:
                # from_addr/to_addrs explícitos = controlamos el envelope MAIL FROM
                # y RCPT TO, en vez de dejar que smtplib los infiera del header.
                # Usamos la dirección de rebotes como envelope MAIL FROM para que los NDR
                # externos (Gmail lleno, dominio inexistente, etc.) no lleguen a mario@.
                from apps.accounts.env_file import read_env_file as _re
                _env = _re()
                _bounce_addr = (_env.get('BOUNCE_EMAIL') or '').strip() or self.user or final_from
                refused = conn.send_message(msg, from_addr=_bounce_addr, to_addrs=[to_email])
            except smtplib.SMTPRecipientsRefused as exc:
                raise EmailSendError(f"Destinatarios rechazados: {exc.recipients}")
            except smtplib.SMTPSenderRefused as exc:
                raise EmailSendError(
                    f"Remitente rechazado ({exc.smtp_code}): {exc.smtp_error}"
                )
            except smtplib.SMTPDataError as exc:
                raise EmailSendError(
                    f"Servidor rechazó el mensaje ({exc.smtp_code}): {exc.smtp_error}"
                )
            except smtplib.SMTPException as exc:
                raise EmailSendError(f"Error SMTP enviando: {exc}")
            if refused:
                raise EmailSendError(f"Destinatarios rechazados: {refused}")
        finally:
            try:
                conn.quit()
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass  # Best-effort cleanup — connection already gone

        return f"smtp-{self.host}-{campaign_id or 'test'}-{subscriber_id or ''}"


class NullSender(BaseEmailSender):
    """No envía nada, solo registra el ID. Para modo local sin proveedor."""
    def send(self, to_email, to_name, from_name, from_email, subject, html,
             campaign_id=None, subscriber_id=None, list_unsubscribe_url=None):
        return f"local-{campaign_id or ''}-{subscriber_id or ''}"


def smtp_config_from_env():
    """SMTP connection config read fresh from the .env file, or None if unset.

    SMTP credentials are stored in .env (not the DB) when saved from the UI, so
    we read them here. Reading the file fresh means changes apply without a
    restart and are seen by every worker process.
    """
    from apps.accounts.env_file import read_env_file

    env = read_env_file()
    host = (env.get("SMTP_HOST") or "").strip()
    if not host:
        return None
    try:
        port = int(env.get("SMTP_PORT") or 587)
    except (TypeError, ValueError):
        port = 587
    return {
        "host": host,
        "port": port,
        "user": env.get("SMTP_USER", ""),
        "password": env.get("SMTP_PASSWORD", ""),
        "use_tls": env.get("SMTP_USE_TLS", "True") == "True",
        "use_ssl": env.get("SMTP_USE_SSL", "False") == "True",
    }


def _build_sender(u) -> "BaseEmailSender | None":
    prov = u.email_provider
    if prov != "local":
        # Prefer SMTP credentials stored in .env; fall back to legacy DB fields
        # (installs that configured SMTP before credentials moved to .env).
        cfg = smtp_config_from_env()
        if cfg:
            # During the transition the password may still live in the DB while
            # the rest has moved to .env — fall back so sending keeps working.
            if not cfg["password"] and u.smtp_password:
                cfg["password"] = u.smtp_password
            return SMTPSender(**cfg)
        if u.smtp_host:
            return SMTPSender(
                host=u.smtp_host,
                port=u.smtp_port or 587,
                user=u.smtp_user,
                password=u.smtp_password,
                use_tls=u.smtp_use_tls,
                use_ssl=u.smtp_use_ssl,
            )
    return None


def get_sender(user) -> BaseEmailSender:
    sender = _build_sender(user)
    if sender:
        return sender
    # Non-admins inherit the shared provider config from the first admin.
    if not user.is_staff:
        from apps.accounts.serializers import get_admin_user
        admin = get_admin_user()
        if admin and admin.id != user.id:
            sender = _build_sender(admin)
            if sender:
                return sender
    return NullSender()
