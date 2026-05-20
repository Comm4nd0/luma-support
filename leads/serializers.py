from rest_framework import serializers

from .models import Lead, LeadActivity


class LeadActivitySerializer(serializers.ModelSerializer):
    actor_email = serializers.SerializerMethodField()
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = LeadActivity
        fields = (
            "id",
            "lead",
            "kind",
            "kind_display",
            "body",
            "actor",
            "actor_email",
            "occurred_at",
            "created_at",
        )
        read_only_fields = ("actor", "actor_email", "created_at")

    def get_actor_email(self, obj) -> str:
        return obj.actor.email if obj.actor_id else ""


class LeadSerializer(serializers.ModelSerializer):
    activities = LeadActivitySerializer(many=True, read_only=True)
    stage_display = serializers.CharField(source="get_stage_display", read_only=True)
    source_display = serializers.CharField(source="get_source_display", read_only=True)
    referring_client_name = serializers.SerializerMethodField()
    converted_client_name = serializers.SerializerMethodField()
    assigned_to_email = serializers.SerializerMethodField()
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Lead
        fields = (
            "id",
            "name",
            "email",
            "phone",
            "company",
            "customer_type",
            "source",
            "source_display",
            "source_detail",
            "referring_client",
            "referring_client_name",
            "interest",
            "estimated_value",
            "stage",
            "stage_display",
            "next_action_at",
            "assigned_to",
            "assigned_to_email",
            "converted_client",
            "converted_client_name",
            "converted_at",
            "lost_reason",
            "is_overdue",
            "activities",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "converted_client",
            "converted_at",
            "created_at",
            "updated_at",
        )

    def get_referring_client_name(self, obj) -> str:
        return obj.referring_client.name if obj.referring_client_id else ""

    def get_converted_client_name(self, obj) -> str:
        return obj.converted_client.name if obj.converted_client_id else ""

    def get_assigned_to_email(self, obj) -> str:
        return obj.assigned_to.email if obj.assigned_to_id else ""
