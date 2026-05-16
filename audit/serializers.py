from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.CharField(source="actor.email", read_only=True)
    target_model = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = (
            "id",
            "actor",
            "actor_email",
            "action",
            "target_model",
            "target_id",
            "target_repr",
            "ip",
            "user_agent",
            "metadata",
            "created_at",
        )
        read_only_fields = fields

    def get_target_model(self, obj):
        return obj.target_ct.model if obj.target_ct_id else None
