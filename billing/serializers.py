from rest_framework import serializers

from .models import Invoice, InvoiceLine, Payment


class InvoiceLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLine
        fields = (
            "id",
            "description",
            "quantity",
            "unit_amount",
            "line_total",
            "account_code",
            "tax_type",
            "time_entry",
        )
        read_only_fields = ("line_total",)


class InvoiceSerializer(serializers.ModelSerializer):
    lines = InvoiceLineSerializer(many=True, required=False)
    kind = serializers.ChoiceField(
        choices=Invoice.Kind.choices, default=Invoice.Kind.ONE_OFF
    )

    class Meta:
        model = Invoice
        fields = (
            "id",
            "client",
            "kind",
            "status",
            "period_start",
            "period_end",
            "subtotal",
            "tax",
            "total",
            "currency",
            "due_date",
            "notes",
            "xero_invoice_id",
            "xero_status",
            "xero_synced_at",
            "sent_at",
            "paid_at",
            "lines",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "status",
            "subtotal",
            "tax",
            "total",
            "xero_invoice_id",
            "xero_status",
            "xero_synced_at",
            "sent_at",
            "paid_at",
            "created_at",
            "updated_at",
        )
        # The partial UniqueConstraint is enforced at DB level — drop the auto
        # UniqueTogetherValidator that would otherwise require period_start.
        validators: list = []

    def create(self, validated_data):
        lines_data = validated_data.pop("lines", [])
        invoice = Invoice.objects.create(**validated_data)
        for line in lines_data:
            InvoiceLine.objects.create(invoice=invoice, **line)
        invoice.recalculate_totals()
        invoice.save(update_fields=["subtotal", "tax", "total", "updated_at"])
        return invoice


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            "id",
            "invoice",
            "xero_payment_id",
            "amount",
            "paid_at",
            "reference",
            "created_at",
        )
