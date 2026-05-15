from rest_framework import serializers

from .models import DeviceToken, Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = (
            "id",
            "user",
            "type",
            "title",
            "body",
            "related_ticket",
            "read",
            "push_sent",
            "created_at",
        )
        read_only_fields = fields


class DeviceTokenSerializer(serializers.ModelSerializer):
    # The viewset handles upsert by token so the unique-validator that DRF
    # would auto-add here must not block a re-registration.
    token = serializers.CharField(max_length=512)

    class Meta:
        model = DeviceToken
        fields = (
            "id",
            "platform",
            "token",
            "app_version",
            "is_active",
            "last_seen_at",
            "created_at",
        )
        read_only_fields = ("id", "is_active", "last_seen_at", "created_at")
