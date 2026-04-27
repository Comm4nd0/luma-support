from rest_framework import serializers

from .models import Attachment, Ticket, TicketNote, TimeEntry


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


class TicketSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.name", read_only=True)
    assigned_to_email = serializers.CharField(
        source="assigned_to.email", read_only=True
    )
    is_breached = serializers.BooleanField(read_only=True)
    total_minutes_logged = serializers.IntegerField(read_only=True)
    time_entries = TimeEntrySerializer(many=True, read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)

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
            "is_breached",
            "assigned_to",
            "assigned_to_email",
            "created_by",
            "resolved_at",
            "closed_at",
            "total_minutes_logged",
            "time_entries",
            "attachments",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "sla_deadline",
            "resolved_at",
            "closed_at",
            "created_at",
            "updated_at",
            "is_breached",
        )


class TicketListSerializer(serializers.ModelSerializer):
    """Lighter serializer for list view — drops nested entries."""

    client_name = serializers.CharField(source="client.name", read_only=True)
    assigned_to_email = serializers.CharField(
        source="assigned_to.email", read_only=True
    )
    is_breached = serializers.BooleanField(read_only=True)

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
            "is_breached",
            "assigned_to",
            "assigned_to_email",
            "created_at",
        )
