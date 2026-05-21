from django.contrib import admin

from .models import CreditNote, Invoice, InvoiceLine, Payment, XeroConnection


@admin.register(CreditNote)
class CreditNoteAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "amount", "currency", "status", "issued_at", "created_at")
    list_filter = ("status", "currency")
    search_fields = ("client__name", "reason", "xero_credit_note_id")
    autocomplete_fields = ("client", "invoice")
    readonly_fields = ("issued_at", "xero_credit_note_id", "stripe_refund_id",
                       "created_at", "updated_at")


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0
    fields = ("description", "quantity", "unit_amount", "line_total", "tax_type")
    readonly_fields = ("line_total",)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "client",
        "kind",
        "status",
        "total",
        "currency",
        "due_date",
        "xero_invoice_id",
        "created_at",
    )
    list_filter = ("kind", "status", "currency")
    search_fields = ("client__name", "xero_invoice_id", "notes")
    readonly_fields = (
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
    inlines = [InvoiceLineInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("xero_payment_id", "invoice", "amount", "paid_at")
    search_fields = ("xero_payment_id", "reference", "invoice__client__name")
    readonly_fields = tuple(f.name for f in Payment._meta.fields)


@admin.register(XeroConnection)
class XeroConnectionAdmin(admin.ModelAdmin):
    list_display = ("tenant_id", "expires_at", "connected_by", "connected_at")
    readonly_fields = (
        "tenant_id",
        "refresh_token_encrypted",
        "access_token",
        "expires_at",
        "connected_at",
        "connected_by",
    )

    def has_add_permission(self, request):
        return not XeroConnection.objects.exists()
