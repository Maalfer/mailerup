from django.db import migrations, models


def api_providers_to_smtp(apps, schema_editor):
    """Quien tuviera Brevo/SendGrid pasa a SMTP genérico (esas integraciones se eliminaron)."""
    User = apps.get_model("accounts", "User")
    User.objects.filter(email_provider__in=["brevo", "sendgrid"]).update(email_provider="smtp_generic")


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_apikey"),
    ]

    operations = [
        migrations.RunPython(api_providers_to_smtp, migrations.RunPython.noop),
        migrations.RemoveField(model_name="user", name="brevo_api_key"),
        migrations.RemoveField(model_name="user", name="sendgrid_api_key"),
        migrations.AlterField(
            model_name="user",
            name="email_provider",
            field=models.CharField(
                choices=[('local', 'Local (no envía)'), ('smtp_generic', 'SMTP genérico'), ('raiola', 'Raiola Networks'), ('gmail', 'Gmail'), ('outlook', 'Outlook / Office 365'), ('yahoo', 'Yahoo Mail'), ('icloud', 'iCloud Mail'), ('zoho', 'Zoho Mail'), ('hostinger', 'Hostinger'), ('ionos', 'IONOS'), ('ovh', 'OVH'), ('dondominio', 'DonDominio'), ('ses', 'Amazon SES (SMTP)'), ('mailgun', 'Mailgun (SMTP)'), ('postmark', 'Postmark (SMTP)'), ('mailjet', 'Mailjet (SMTP)'), ('sparkpost', 'SparkPost (SMTP)'), ('resend', 'Resend (SMTP)')],
                default='local', max_length=20,
            ),
        ),
    ]
