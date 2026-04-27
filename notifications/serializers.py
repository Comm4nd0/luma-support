from rest_framework import serializers

from .models import Notification


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
