import uuid
from django.conf import settings
from django.db import models


class SubscriberList(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lists")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def subscriber_count(self):
        return self.subscribers.filter(status="active").count()


class Subscriber(models.Model):
    STATUS = [
        ("active", "Activo"),
        ("unsubscribed", "Dado de baja"),
        ("bounced", "Rebotado"),
        ("complained", "Queja spam"),
    ]
    LIFECYCLE_STAGES = [
        ("lead", "Lead"),
        ("nurturing", "Nutriendo"),
        ("mql", "Cualificado (MQL)"),
        ("cliente", "Cliente"),
        ("baja", "Baja de interés"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    list = models.ForeignKey(SubscriberList, on_delete=models.CASCADE, related_name="subscribers")
    email = models.EmailField()
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default="active")
    subscribed_at = models.DateTimeField(auto_now_add=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    # Ciclo de vida / nivel de consciencia (Eugene Schwartz) para poder excluir
    # compradores de campañas de venta y nutrir según en qué punto está cada uno.
    lifecycle_stage = models.CharField(max_length=20, choices=LIFECYCLE_STAGES, default="lead")
    awareness_level = models.PositiveSmallIntegerField(default=1)
    last_purchase_at = models.DateTimeField(null=True, blank=True)

    # Trazabilidad de origen (first-touch: se fija al confirmar el alta y no se pisa).
    # Se rellena en forms.VerifySubscriptionView desde el SignupAttempt. Ver docs/TRAZABILIDAD.md.
    #   source: manychat | email | web | <utm_source> | import | manual | api | "" (desconocido)
    #   attribution_method: captured (viajó con el formulario) | inferred (reconstruido después) | ""
    source = models.CharField(max_length=30, blank=True, default="", db_index=True)
    utm_source = models.CharField(max_length=100, blank=True, default="")
    utm_medium = models.CharField(max_length=100, blank=True, default="")
    utm_campaign = models.CharField(max_length=100, blank=True, default="")
    utm_content = models.CharField(max_length=100, blank=True, default="")
    landing_path = models.CharField(max_length=200, blank=True, default="")
    referrer_host = models.CharField(max_length=100, blank=True, default="")
    manychat_sid = models.CharField(max_length=40, blank=True, default="", db_index=True)
    manychat_pid = models.CharField(max_length=40, blank=True, default="")
    visitor_id = models.CharField(max_length=40, blank=True, default="", db_index=True)
    attribution_method = models.CharField(max_length=12, blank=True, default="")

    class Meta:
        unique_together = ("list", "email")
        ordering = ["-subscribed_at"]

    def __str__(self):
        return self.email


class ScoringCursor(models.Model):
    """Fila única: marca hasta qué momento se procesaron aperturas/clics para
    el scoring automático de awareness_level (apps/subscribers/scoring.py)."""
    last_run_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
