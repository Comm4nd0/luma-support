from django.contrib import admin

from .models import Quote, QuoteLine


class QuoteLineInline(admin.TabularInline):
    model = QuoteLine
    extra = 0
    fields = ("description", "quantity", "unit_amount", "line_total")
    readonly_fields = ("line_total",)


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "client",
        "lead",
        "status",
        "total",
        "valid_until",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("number", "client__name", "lead__name", "notes")
    readonly_fields = (
        "number",
        "accept_token",
        "sent_at",
        "accepted_at",
        "accepted_by_name",
        "accepted_ip",
        "rejected_at",
        "subtotal",
        "total",
        "converted_invoice",
        "created_at",
        "updated_at",
    )
    inlines = [QuoteLineInline]


@admin.register(QuoteLine)
class QuoteLineAdmin(admin.ModelAdmin):
    list_display = ("quote", "description", "quantity", "unit_amount", "line_total")
    search_fields = ("description", "quote__number")
