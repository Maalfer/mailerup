from rest_framework import serializers
from .models import SubscriberList, Subscriber


class SubscriberListSerializer(serializers.ModelSerializer):
    subscriber_count = serializers.ReadOnlyField()

    class Meta:
        model = SubscriberList
        fields = ("id", "name", "description", "subscriber_count", "created_at")
        read_only_fields = ("id", "created_at")


class SubscriberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscriber
        fields = (
            "id", "email", "first_name", "last_name", "status",
            "subscribed_at", "unsubscribed_at",
            "lifecycle_stage", "awareness_level", "last_purchase_at",
        )
        read_only_fields = ("id", "subscribed_at")
