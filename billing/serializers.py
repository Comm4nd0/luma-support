from rest_framework import serializers

from .models import Invoice, InvoiceLine, Payment


class InvoiceLineSerializer(serializers.ModelSerializer):
    # `id` is writable so the parent invoice's `update()` can diff incoming
    # lines against existing rows; we override the default ModelSerializer
    # behaviour (which would drop `id` as read-only).
    id = serializers.IntegerField(required=False)

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

    def update(self, instance, validated_data):
        # Lines are managed as a full replacement: existing rows matched by
        # `id` are updated, unmatched survivors deleted, items without `id`
        # created. Totals are recomputed once at the end.
        lines_data = validated_data.pop("lines", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()

        if lines_data is not None:
            existing = {line.pk: line for line in instance.lines.all()}
            seen_ids: set[int] = set()
            for payload in lines_data:
                line_id = payload.pop("id", None)
                if line_id is not None and line_id in existing:
                    line = existing[line_id]
                    for f, v in payload.items():
                        setattr(line, f, v)
                    line.save()
                    seen_ids.add(line_id)
                else:
                    InvoiceLine.objects.create(invoice=instance, **payload)
            for pk, line in existing.items():
                if pk not in seen_ids:
                    line.delete()

        # The viewset prefetches `lines`; that cache is now stale, and
        # `recalculate_totals` walks `self.lines.all()`.
        if hasattr(instance, "_prefetched_objects_cache"):
            instance._prefetched_objects_cache.pop("lines", None)
        instance.recalculate_totals()
        instance.save(update_fields=["subtotal", "tax", "total", "updated_at"])
        return instance


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
