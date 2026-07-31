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
    clicked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-clicked_at"]
