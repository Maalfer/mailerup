import uuid
from django.db import models


class EmailOpen(models.Model):
    campaign = models.ForeignKey("campaigns.Campaign", on_delete=models.CASCADE, related_name="opens")
    subscriber = models.ForeignKey("subscribers.Subscriber", on_delete=models.CASCADE)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    opened_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-opened_at"]


class EmailClick(models.Model):
    campaign = models.ForeignKey("campaigns.Campaign", on_delete=models.CASCADE, related_name="clicks")
    subscriber = models.ForeignKey("subscribers.Subscriber", on_delete=models.CASCADE)
    url = models.URLField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    clicked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-clicked_at"]


class EmailBounce(models.Model):
    BOUNCE_TYPES = [("hard", "Duro"), ("soft", "Suave")]
    # Nullable: el rebote (NDR) solo trae el email del destinatario, no a qué
    # campaña pertenecía. Se atribuye best-effort al CampaignSend más reciente
    # de ese suscriptor; si no hay ninguno (p.ej. vino de una automatización)
    # se guarda sin campaña.
    campaign = models.ForeignKey(
        "campaigns.Campaign", on_delete=models.CASCADE, related_name="bounces",
        null=True, blank=True,
    )
    subscriber = models.ForeignKey("subscribers.Subscriber", on_delete=models.CASCADE)
    bounce_type = models.CharField(max_length=10, choices=BOUNCE_TYPES)
    reason = models.CharField(max_length=500, blank=True)
    bounced_at = models.DateTimeField(auto_now_add=True)


class EmailUnsubscribe(models.Model):
    campaign = models.ForeignKey("campaigns.Campaign", on_delete=models.CASCADE, null=True, related_name="unsubscribes")
    subscriber = models.ForeignKey("subscribers.Subscriber", on_delete=models.CASCADE)
    reason = models.CharField(max_length=500, blank=True)
    unsubscribed_at = models.DateTimeField(auto_now_add=True)


class AutomationEmailOpen(models.Model):
    """Apertura de un correo de un paso de automatización (espeja EmailOpen)."""
    step = models.ForeignKey(
        "automations.AutomationStep", on_delete=models.CASCADE, related_name="opens"
    )
    subscriber = models.ForeignKey("subscribers.Subscriber", on_delete=models.CASCADE)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    opened_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-opened_at"]


class AutomationEmailClick(models.Model):
    """Clic en un correo de un paso de automatización (espeja EmailClick)."""
    step = models.ForeignKey(
        "automations.AutomationStep", on_delete=models.CASCADE, related_name="clicks"
    )
    subscriber = models.ForeignKey("subscribers.Subscriber", on_delete=models.CASCADE)
    url = models.URLField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True, default="")
    clicked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-clicked_at"]


class _AttributionFields(models.Model):
    """Campos de origen comunes a visitas e intentos de alta."""
    source = models.CharField(max_length=30, blank=True, default="", db_index=True)
    utm_source = models.CharField(max_length=100, blank=True, default="")
    utm_medium = models.CharField(max_length=100, blank=True, default="")
    utm_campaign = models.CharField(max_length=100, blank=True, default="")
    utm_content = models.CharField(max_length=100, blank=True, default="")
    manychat_sid = models.CharField(max_length=40, blank=True, default="")
    manychat_pid = models.CharField(max_length=40, blank=True, default="")
    referrer_host = models.CharField(max_length=100, blank=True, default="")
    visitor_id = models.CharField(max_length=40, blank=True, default="", db_index=True)

    class Meta:
        abstract = True


class LandingVisit(_AttributionFields):
    """Visita a una página de captación (beacon JS de la web). Parte alta del embudo:
    visita -> formulario enviado -> alta confirmada -> secuencia -> compra."""
    path = models.CharField(max_length=200, blank=True, default="")
    user_agent = models.CharField(max_length=300, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


class SignupAttempt(_AttributionFields):
    """Cada envío del formulario de suscripción (doble opt-in). Permite medir cuánta gente
    envía el formulario pero nunca confirma el correo."""
    OUTCOMES = [("pending", "Pendiente de confirmar"), ("confirmed", "Confirmado"),
                ("already_subscribed", "Ya suscrito")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    form = models.ForeignKey("subscription_forms.SubscriptionForm", null=True, blank=True,
                             on_delete=models.SET_NULL, related_name="attempts")
    email = models.CharField(max_length=254, db_index=True)
    outcome = models.CharField(max_length=20, choices=OUTCOMES, default="pending")
    landing_path = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    subscriber = models.ForeignKey("subscribers.Subscriber", null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="signup_attempts")


class Purchase(models.Model):
    """Copia en MailerUp de los pagos de la tienda (tabla `payments` de elrincondelhacker),
    sincronizada por scripts/sync_compras.py. `mailerup_sid` es el ID del suscriptor que llegó
    desde un enlace de correo (parámetro `mu`): atribución exacta; si falta se casa por email."""
    stripe_session_id = models.CharField(max_length=255, unique=True)
    email = models.CharField(max_length=254, db_index=True)
    subscriber = models.ForeignKey("subscribers.Subscriber", null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="purchases")
    item_type = models.CharField(max_length=10, blank=True, default="")
    item_title = models.CharField(max_length=255, blank=True, default="")
    amount_cents = models.IntegerField(default=0)
    refunded_cents = models.IntegerField(default=0)
    origin = models.CharField(max_length=20, blank=True, default="")
    paid_at = models.DateTimeField(db_index=True)
    utm_source = models.CharField(max_length=100, blank=True, default="")
    utm_medium = models.CharField(max_length=100, blank=True, default="")
    utm_campaign = models.CharField(max_length=100, blank=True, default="")
    utm_content = models.CharField(max_length=100, blank=True, default="")
    mailerup_sid = models.CharField(max_length=40, blank=True, default="")
    attribution = models.CharField(max_length=10, blank=True, default="")  # mu | email | ""
    synced_at = models.DateTimeField(auto_now=True)
