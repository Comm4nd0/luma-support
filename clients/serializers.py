from rest_framework import serializers

from .models import Client, System


class SystemSerializer(serializers.ModelSerializer):
    # Write-only field that encrypts before save; never echoed back in plaintext.
    credentials = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )

    class Meta:
        model = System
        fields = (
            "id",
            "client",
            "type",
            "name",
            "description",
            "devices_json",
            "credentials",
            "monitoring_url",
            "installed_date",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")

    def create(self, validated_data):
        creds = validated_data.pop("credentials", "")
        instance = System(**validated_data)
        if creds:
            instance.set_credentials(creds)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        creds = validated_data.pop("credentials", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if creds is not None:
            instance.set_credentials(creds)
        instance.save()
        return instance


class ClientSerializer(serializers.ModelSerializer):
    systems = SystemSerializer(many=True, read_only=True)
    open_ticket_count = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = (
            "id",
            "name",
            "company",
            "email",
            "phone",
            "address",
            "customer_type",
            "vat_number",
            "billing_address",
            "care_plan_tier",
            "care_plan_start",
            "care_plan_renewal",
            "hourly_rate",
            "monthly_fee",
            "xero_contact_id",
            "xero_synced_at",
            "notes",
            "systems",
            "open_ticket_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "xero_contact_id",
            "xero_synced_at",
            "created_at",
            "updated_at",
        )

    def get_open_ticket_count(self, obj) -> int:
        from tickets.models import Ticket

        return obj.tickets.exclude(
            status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED]
        ).count()
