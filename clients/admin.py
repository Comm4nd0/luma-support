from django.contrib import admin

from .models import Client, Contact, System


class SystemInline(admin.TabularInline):
    model = System
    extra = 0
    fields = ("type", "name", "monitoring_url", "installed_date")
    show_change_link = True


class ContactInline(admin.TabularInline):
    model = Contact
    extra = 0
    fields = ("name", "email", "phone", "title", "is_primary")


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "company",
        "customer_type",
        "email",
        "care_plan_tier",
        "monthly_fee",
        "hourly_rate",
        "care_plan_renewal",
    )
    list_filter = ("customer_type", "care_plan_tier")
    search_fields = ("name", "company", "email", "vat_number")
    readonly_fields = ("xero_contact_id", "xero_synced_at")
    inlines = [ContactInline, SystemInline]


@admin.register(System)
class SystemAdmin(admin.ModelAdmin):
    list_display = ("name", "client", "type", "installed_date", "monitoring_url")
    list_filter = ("type",)
    search_fields = ("name", "client__name", "description")
    readonly_fields = ("credentials_encrypted",)


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("name", "client", "email", "phone", "title", "is_primary")
    list_filter = ("is_primary",)
    search_fields = ("name", "email", "client__name")
