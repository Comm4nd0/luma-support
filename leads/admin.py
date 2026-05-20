from django.contrib import admin

from .models import Lead, LeadActivity


class LeadActivityInline(admin.TabularInline):
    model = LeadActivity
    extra = 0
    fields = ("kind", "body", "actor", "occurred_at")
    readonly_fields = ("created_at",)


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "company",
        "stage",
        "source",
        "estimated_value",
        "next_action_at",
        "assigned_to",
        "created_at",
    )
    list_filter = ("stage", "source", "customer_type", "assigned_to")
    search_fields = ("name", "email", "company", "interest")
    readonly_fields = (
        "converted_client",
        "converted_at",
        "last_reminded_at",
        "created_at",
        "updated_at",
    )
    inlines = [LeadActivityInline]


@admin.register(LeadActivity)
class LeadActivityAdmin(admin.ModelAdmin):
    list_display = ("lead", "kind", "actor", "occurred_at")
    list_filter = ("kind",)
    search_fields = ("body", "lead__name")
