from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import PROVIDER_CHOICES
from apps.accounts.views import PROVIDER_PRESETS
from apps.integrations.email_sender import NullSender, SMTPSender, get_sender

User = get_user_model()


class SmtpOnlyTests(TestCase):
    """MailerUp envía solo por SMTP: no hay integraciones por API."""

    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", username="admin", password="x", is_staff=True
        )

    def test_no_api_providers_in_choices_or_presets(self):
        keys = {k for k, _ in PROVIDER_CHOICES}
        self.assertNotIn("brevo", keys)
        self.assertNotIn("sendgrid", keys)
        self.assertEqual(set(PROVIDER_PRESETS), keys)
        self.assertNotIn("api", {p["kind"] for p in PROVIDER_PRESETS.values()})

    def test_user_model_has_no_api_key_fields(self):
        names = {f.name for f in User._meta.get_fields()}
        self.assertNotIn("brevo_api_key", names)
        self.assertNotIn("sendgrid_api_key", names)

    def test_me_endpoint_does_not_expose_api_key_fields(self):
        client = APIClient()
        client.force_authenticate(self.admin)
        data = client.get("/api/auth/me/").json()
        self.assertFalse([k for k in data if "brevo" in k or "sendgrid" in k])
        self.assertNotIn("smtp_password", data)

    def test_local_provider_does_not_send(self):
        self.admin.email_provider = "local"
        self.assertIsInstance(get_sender(self.admin), NullSender)

    def test_smtp_provider_builds_smtp_sender_from_db_fields(self):
        self.admin.email_provider = "smtp_generic"
        self.admin.smtp_host = "smtp.example.com"
        self.admin.smtp_user = "a@example.com"
        self.admin.smtp_password = "pw"
        sender = get_sender(self.admin)
        # Las credenciales pueden venir del .env (si existe) o de la BD; en ambos
        # casos el remitente debe ser SMTP, nunca una API.
        self.assertIsInstance(sender, SMTPSender)
