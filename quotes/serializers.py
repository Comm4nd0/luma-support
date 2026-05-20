from rest_framework import serializers

from .models import Quote, QuoteLine


class QuoteLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuoteLine
        fields = (
            "id",
            "description",
            "quantity",
            "unit_amount",
            "line_total",
            "account_code",
            "tax_type",
        )
        read_only_fields = ("line_total",)


class QuoteSerializer(serializers.ModelSerializer):
    lines = QuoteLineSerializer(many=True, required=False)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    recipient_name = serializers.CharField(read_only=True)
    recipient_email = serializers.CharField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = Quote
        fields = (
            "id",
            "number",
            "lead",
            "client",
            "status",
            "status_display",
            "valid_until",
            "subtotal",
            "tax",
            "total",
            "currency",
            "notes",
            "accept_token",
            "sent_at",
            "accepted_at",
            "accepted_by_name",
            "rejected_at",
            "rejection_reason",
            "converted_invoice",
            "recipient_name",
            "recipient_email",
            "is_expired",
            "lines",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "number",
            "accept_token",
            "sent_at",
            "accepted_at",
            "accepted_by_name",
            "rejected_at",
            "rejection_reason",
            "converted_invoice",
            "subtotal",
            "total",
            "created_at",
            "updated_at",
        )

    def create(self, validated_data):
        lines_data = validated_data.pop("lines", [])
        quote = Quote.objects.create(**validated_data)
        for line in lines_data:
            QuoteLine.objects.create(quote=quote, **line)
        quote.recalculate_totals()
        quote.save(update_fields=["subtotal", "total"])
        return quote

    def update(self, instance, validated_data):
        lines_data = validated_data.pop("lines", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        if lines_data is not None:
            instance.lines.all().delete()
            for line in lines_data:
                QuoteLine.objects.create(quote=instance, **line)
            instance.recalculate_totals()
            instance.save(update_fields=["subtotal", "total"])
        return instance
