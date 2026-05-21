from rest_framework import serializers

from .models import Client, ClientDocument, Contact, ReferralCode, SiteVisit, System


class ClientDocumentSerializer(serializers.ModelSerializer):
    uploaded_by_email = serializers.CharField(
        source="uploaded_by.email", read_only=True
    )
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = ClientDocument
        fields = (
            "id",
            "client",
            "title",
            "file",
            "file_url",
            "kind",
            "client_visible",
            "uploaded_by",
            "uploaded_by_email",
            "uploaded_at",
        )
        read_only_fields = (
            "file_url",
            "uploaded_by",
            "uploaded_by_email",
            "uploaded_at",
        )

    def get_file_url(self, obj) -> str:
        request = self.context.get("request")
        if not obj.file:
            return ""
        url = obj.file.url
        return request.build_absolute_uri(url) if request else url


class SiteVisitSerializer(serializers.ModelSerializer):
    duration_minutes = serializers.IntegerField(read_only=True)
    user_email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = SiteVisit
        fields = (
            "id",
            "client",
            "user",
            "user_email",
            "started_at",
            "ended_at",
            "lat_start",
            "lon_start",
            "lat_end",
            "lon_end",
            "notes",
            "duration_minutes",
            "time_entry",
        )
        read_only_fields = (
            "user",
            "user_email",
            "started_at",
            "ended_at",
            "duration_minutes",
            "time_entry",
        )


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = (
            "id",
            "client",
            "name",
            "email",
            "phone",
            "title",
            "is_primary",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")


class SystemSerializer(serializers.ModelSerializer):
    # Write-only field that encrypts before save; never echoed back in plaintext.
    credentials = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )
    # Read-only "we hold credentials for this system" flag — visible to
    # clients so they can see a padlock icon and request rotation
    # without ever seeing the plaintext secret.
    credentials_present = serializers.SerializerMethodField()

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
            "credentials_present",
            "monitoring_url",
            "installed_date",
            "last_checked_at",
            "health_status",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "last_checked_at",
            "health_status",
            "devices_json",
            "created_at",
            "updated_at",
        )

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

    def get_credentials_present(self, obj) -> bool:
        return bool(getattr(obj, "credentials_encrypted", ""))


class ClientSerializer(serializers.ModelSerializer):
    systems = SystemSerializer(many=True, read_only=True)
    contacts = ContactSerializer(many=True, read_only=True)
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
            "contacts",
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


class ReferralCodeSerializer(serializers.ModelSerializer):
    referrals = serializers.SerializerMethodField()

    class Meta:
        model = ReferralCode
        fields = (
            "code",
            "credit_balance",
            "lifetime_credit",
            "referrals",
        )

    def get_referrals(self, obj) -> list[dict]:
        out = []
        for lead in obj.client.referrals.order_by("-created_at")[:50]:
            out.append(
                {
                    "name": lead.name,
                    "stage": lead.stage,
                    "stage_display": lead.get_stage_display(),
                    "created_at": lead.created_at.isoformat(),
                }
            )
        return out
