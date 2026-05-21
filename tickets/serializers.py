from rest_framework import serializers

from .models import (
    Attachment,
    CsatResponse,
    MaintenanceSchedule,
    SavedTicketFilter,
    Ticket,
    TicketNote,
    TicketTag,
    TicketTemplate,
    TimeEntry,
)


class SavedTicketFilterSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedTicketFilter
        fields = ("id", "name", "querystring", "pinned", "sort_order", "created_at")
        read_only_fields = ("created_at",)


class TicketTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketTemplate
        fields = (
            "id",
            "name",
            "body",
            "public_default",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")


class TicketTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketTag
        fields = ("id", "name", "slug", "color")
        read_only_fields = ("slug",)

    def create(self, validated_data):
        from django.utils.text import slugify

        validated_data.setdefault("slug", slugify(validated_data["name"]))
        return super().create(validated_data)


class TimeEntrySerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = TimeEntry
        fields = (
            "id",
            "ticket",
            "user",
            "user_email",
            "minutes",
            "description",
            "billable",
            "created_at",
        )
        read_only_fields = ("user", "created_at")


class AttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = (
            "id",
            "ticket",
            "file",
            "filename",
            "uploaded_by",
            "uploaded_at",
        )
        read_only_fields = ("uploaded_by", "uploaded_at", "filename")


class TicketNoteSerializer(serializers.ModelSerializer):
    author_email = serializers.CharField(source="author.email", read_only=True)

    class Meta:
        model = TicketNote
        fields = (
            "id",
            "ticket",
            "author",
            "author_email",
            "body",
            "internal",
            "created_at",
        )
        read_only_fields = ("author", "created_at")


class CsatResponseSerializer(serializers.ModelSerializer):
    """Public view of a CSAT — exclude the token so it can never leak."""

    class Meta:
        model = CsatResponse
        fields = ("id", "rating", "comment", "requested_at", "responded_at")
        read_only_fields = fields


class TicketSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.name", read_only=True)
    assigned_to_email = serializers.CharField(
        source="assigned_to.email", read_only=True
    )
    is_breached = serializers.BooleanField(read_only=True)
    is_paused = serializers.BooleanField(read_only=True)
    effective_sla_deadline = serializers.DateTimeField(read_only=True)
    total_minutes_logged = serializers.IntegerField(read_only=True)
    time_entries = TimeEntrySerializer(many=True, read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)
    csat = CsatResponseSerializer(read_only=True)
    tags = TicketTagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        write_only=True,
        required=False,
        queryset=TicketTag.objects.all(),
        source="tags",
    )

    class Meta:
        model = Ticket
        fields = (
            "id",
            "client",
            "client_name",
            "system",
            "subject",
            "description",
            "priority",
            "status",
            "sla_deadline",
            "sla_paused_at",
            "effective_sla_deadline",
            "is_breached",
            "is_paused",
            "assigned_to",
            "assigned_to_email",
            "created_by",
            "resolved_at",
            "closed_at",
            "total_minutes_logged",
            "time_entries",
            "attachments",
            "csat",
            "tags",
            "tag_ids",
            "client_last_viewed_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "sla_deadline",
            "sla_paused_at",
            "effective_sla_deadline",
            "resolved_at",
            "closed_at",
            "created_at",
            "updated_at",
            "is_breached",
            "is_paused",
        )


class TicketListSerializer(serializers.ModelSerializer):
    """Lighter serializer for list view — drops nested entries."""

    client_name = serializers.CharField(source="client.name", read_only=True)
    assigned_to_email = serializers.CharField(
        source="assigned_to.email", read_only=True
    )
    is_breached = serializers.BooleanField(read_only=True)
    is_paused = serializers.BooleanField(read_only=True)
    effective_sla_deadline = serializers.DateTimeField(read_only=True)
    tags = TicketTagSerializer(many=True, read_only=True)

    class Meta:
        model = Ticket
        fields = (
            "id",
            "subject",
            "client",
            "client_name",
            "priority",
            "status",
            "sla_deadline",
            "effective_sla_deadline",
            "is_breached",
            "is_paused",
            "assigned_to",
            "assigned_to_email",
            "tags",
            "created_at",
        )


class MaintenanceScheduleSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.name", read_only=True)
    system_name = serializers.CharField(source="system.name", read_only=True)

    class Meta:
        model = MaintenanceSchedule
        fields = (
            "id",
            "client",
            "client_name",
            "system",
            "system_name",
            "cadence",
            "next_run_at",
            "template_subject",
            "template_description",
            "priority",
            "default_assignee",
            "active",
            "last_run_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("last_run_at", "created_at", "updated_at")
