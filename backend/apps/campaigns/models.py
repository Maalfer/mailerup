import uuid
import re
import os
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.conf import settings


class Resource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='resources')
    original_name = models.CharField(max_length=255)
    stored_name = models.CharField(max_length=255, unique=True)
    content_type = models.CharField(max_length=100, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.original_name

    @property
    def public_url(self):
        return f'/recurso/{self.stored_name}'

    @staticmethod
    def make_stored_name(original_name):
        base, ext = os.path.splitext(original_name)
        slug = re.sub(r'[^\w\-]', '_', base).strip('_').lower() or 'archivo'
        candidate = slug + ext.lower()
        if not Resource.objects.filter(stored_name=candidate).exists():
            return candidate
        short_id = uuid.uuid4().hex[:6]
        return f'{slug}_{short_id}{ext.lower()}'


class Campaign(models.Model):
    STATUS = [
        ('draft', 'Borrador'),
        ('scheduled', 'Programada'),
        ('sending', 'Enviando'),
        ('sent', 'Enviada'),
        ('paused', 'Pausada'),
        ('failed', 'Fallida'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='campaigns')
    name = models.CharField(max_length=250)
    subject = models.CharField(max_length=250)
    preview_text = models.CharField(max_length=250, blank=True)
    from_name = models.CharField(max_length=150, blank=True, default='')
    from_email = models.EmailField(blank=True, default='')
    reply_to = models.EmailField(blank=True)
    html_content = models.TextField()
    plain_content = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='draft')
    subscriber_list = models.ForeignKey(
        'subscribers.SubscriberList', on_delete=models.SET_NULL, null=True, related_name='campaigns'
    )
    # Si True, la campaña se envía a TODOS los grupos del usuario (deduplicando por
    # email), ignorando subscriber_list.
    send_to_all = models.BooleanField(default=False)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    excluded_emails = models.TextField(blank=True, default='')
    # A/B testing
    ab_enabled = models.BooleanField(default=False)
    subject_b = models.CharField(max_length=250, blank=True)
    ab_split_percent = models.IntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def stats(self):
        sends = self.sends.all()
        total = sends.count()
        if total == 0:
            return {'total': 0, 'delivered': 0, 'opens': 0, 'clicks': 0, 'unsubscribes': 0, 'bounces': 0}
        from apps.analytics.models import EmailOpen, EmailClick
        # Las tasas se calculan sobre lo entregado, no sobre lo intentado: un
        # envío que falló nunca pudo abrirse ni clicarse.
        delivered = sends.exclude(provider_message_id__startswith='error:').count()
        opens = EmailOpen.objects.filter(campaign=self).values('subscriber').distinct().count()
        clicks = EmailClick.objects.filter(campaign=self).values('subscriber').distinct().count()
        return {
            'total': total,
            'delivered': delivered,
            'opens': opens,
            'clicks': clicks,
            'open_rate': round(opens / delivered * 100, 1) if delivered else 0,
            'click_rate': round(clicks / delivered * 100, 1) if delivered else 0,
        }


class CampaignSend(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='sends')
    subscriber = models.ForeignKey('subscribers.Subscriber', on_delete=models.CASCADE)
    sent_at = models.DateTimeField(auto_now_add=True)
    provider_message_id = models.CharField(max_length=255, blank=True)
    ab_variant = models.CharField(max_length=1, blank=True, default='')

    class Meta:
        unique_together = ('campaign', 'subscriber')
