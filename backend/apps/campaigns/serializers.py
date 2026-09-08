from rest_framework import serializers
from apps.subscribers.models import SubscriberList, Subscriber
from .models import Campaign, Resource


class ResourceSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Resource
        fields = ('id', 'original_name', 'stored_name', 'url', 'content_type', 'file_size', 'uploaded_at')
        read_only_fields = fields

    def get_url(self, obj):
        return obj.public_url


class CampaignSerializer(serializers.ModelSerializer):
    stats = serializers.ReadOnlyField()
    from_name = serializers.CharField(required=False, allow_blank=True, default='')
    from_email = serializers.CharField(required=False, allow_blank=True, default='')
    subscriber_list = serializers.PrimaryKeyRelatedField(
        required=False, allow_null=True, queryset=SubscriberList.objects.none(),
    )

    class Meta:
        model = Campaign
        fields = (
            'id', 'name', 'subject', 'preview_text', 'from_name', 'from_email',
            'reply_to', 'html_content', 'plain_content', 'status',
            'subscriber_list', 'send_to_all', 'scheduled_at', 'sent_at',
            'created_at', 'stats',
            'ab_enabled', 'subject_b', 'ab_split_percent',
            'excluded_emails',
            'segment_lifecycle_stages', 'segment_exclude_customers',
            'segment_min_awareness', 'segment_max_awareness',
        )
        read_only_fields = ('id', 'status', 'sent_at', 'created_at', 'stats')

    def validate_segment_lifecycle_stages(self, value):
        valid = dict(Subscriber.LIFECYCLE_STAGES)
        if not isinstance(value, list) or any(v not in valid for v in value):
            raise serializers.ValidationError(
                f"Valores válidos: {', '.join(valid)}"
            )
        return value

    def validate_segment_min_awareness(self, value):
        if value is not None and not (1 <= value <= 5):
            raise serializers.ValidationError("Debe estar entre 1 y 5.")
        return value

    def validate_segment_max_awareness(self, value):
        if value is not None and not (1 <= value <= 5):
            raise serializers.ValidationError("Debe estar entre 1 y 5.")
        return value

    def get_fields(self):
        # Restringe subscriber_list a las listas del propietario (admin compartido
        # o el propio usuario). Evita IDOR: sin esto, cualquier ID de lista de otra
        # cuenta sería aceptado (CWE-639).
        fields = super().get_fields()
        request = self.context.get('request')
        if request is not None and request.user.is_authenticated:
            from apps.accounts.serializers import get_admin_user
            owner = get_admin_user() or request.user
            fields['subscriber_list'].queryset = SubscriberList.objects.filter(user=owner)
        return fields


class CampaignListSerializer(serializers.ModelSerializer):
    stats = serializers.ReadOnlyField()

    class Meta:
        model = Campaign
        fields = ('id', 'name', 'subject', 'status', 'scheduled_at', 'sent_at', 'created_at', 'stats')
