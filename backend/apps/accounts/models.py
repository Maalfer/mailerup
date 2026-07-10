import hashlib
import secrets
import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('El email es obligatorio')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


PROVIDER_CHOICES = [
    ("local", "Local (no envía)"),
    ("smtp_generic", "SMTP genérico"),
    ("raiola", "Raiola Networks"),
    ("gmail", "Gmail"),
    ("outlook", "Outlook / Office 365"),
    ("yahoo", "Yahoo Mail"),
    ("icloud", "iCloud Mail"),
    ("zoho", "Zoho Mail"),
    ("hostinger", "Hostinger"),
    ("ionos", "IONOS"),
    ("ovh", "OVH"),
    ("dondominio", "DonDominio"),
    ("ses", "Amazon SES (SMTP)"),
    ("mailgun", "Mailgun (SMTP)"),
    ("postmark", "Postmark (SMTP)"),
    ("mailjet", "Mailjet (SMTP)"),
    ("sparkpost", "SparkPost (SMTP)"),
    ("resend", "Resend (SMTP)"),
    ("brevo", "Brevo (API)"),
    ("sendgrid", "SendGrid (API)"),
]


class User(AbstractUser):
    objects = UserManager()

    email = models.EmailField(unique=True)
    company = models.CharField(max_length=150, blank=True)
    timezone = models.CharField(max_length=50, default="Europe/Madrid")
    brevo_api_key = models.CharField(max_length=255, blank=True)
    sendgrid_api_key = models.CharField(max_length=255, blank=True)
    email_provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES,
        default="local",
    )
    smtp_host = models.CharField(max_length=255, blank=True)
    smtp_port = models.IntegerField(default=587)
    smtp_user = models.CharField(max_length=255, blank=True)
    smtp_password = models.CharField(max_length=255, blank=True)
    smtp_use_tls = models.BooleanField(default=True)
    smtp_use_ssl = models.BooleanField(default=False)
    from_email = models.EmailField(blank=True)
    from_name = models.CharField(max_length=150, blank=True)

    footer_company = models.CharField(max_length=200, blank=True, default="")
    footer_address = models.CharField(max_length=300, blank=True, default="")
    footer_unsubscribe_text = models.CharField(
        max_length=300,
        blank=True,
        default="Si ya no quieres recibir nuestros correos, puedes darte de baja en cualquier momento.",
    )
    footer_button_label = models.CharField(max_length=80, blank=True, default="Darse de baja")
    # Líneas extra del pie (configurables; vacías = no se muestran). Default genérico
    # para "reenviar"; la de "suscribirse" queda vacía (la rellena cada instancia).
    footer_forward_text = models.CharField(
        max_length=300, blank=True,
        default="Si te ha gustado este email, reenvíaselo a un compañero.",
    )
    footer_subscribe_text = models.CharField(max_length=300, blank=True, default="")

    # Ritmo de envío de campañas (correos/hora), configurable desde Ajustes. El
    # scheduler in-process lo lee en caliente y reparte la tasa suavemente.
    send_rate_per_hour = models.PositiveIntegerField(default=300)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return self.email


def hash_api_key(raw):
    """SHA-256 hex of a raw API key. Deterministic lookup value (the raw key is
    high-entropy random, so a plain hash — not a slow password hash — is fine)."""
    return hashlib.sha256(raw.encode()).hexdigest()


class ApiKey(models.Model):
    """Credential for the external subscriber-creation endpoint. The raw key is
    shown ONCE at creation and never stored; only its SHA-256 hash is persisted."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_keys"
    )
    name = models.CharField(max_length=100, blank=True)      # etiqueta humana, p.ej. "Landing page"
    prefix = models.CharField(max_length=12, db_index=True)  # primeros caracteres del key, solo para mostrar
    hashed_key = models.CharField(max_length=64, unique=True)  # sha256 hex del key completo
    is_active = models.BooleanField(default=True)            # revocar = poner False
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name or 'API key'} ({self.prefix}…)"

    @classmethod
    def generate(cls, user, name=""):
        """Create an ApiKey and return (instance, raw_key). raw_key is only
        available here — it is never recoverable afterwards."""
        raw = secrets.token_urlsafe(32)
        instance = cls.objects.create(
            user=user,
            name=name,
            prefix=raw[:8],
            hashed_key=hash_api_key(raw),
        )
        return instance, raw
