from django.contrib import admin

from .models import Client, System


class SystemInline(admin.TabularInline):
    model = System
    extra = 0
    fields = ("type", "name", "monitoring_url", "installed_date")
    show_change_link = True


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "company",
        "email",
        "care_plan_tier",
        "care_plan_renewal",
    )
    list_filter = ("care_plan_tier",)
    search_fields = ("name", "company", "email")
    inlines = [SystemInline]


@admin.register(System)
class SystemAdmin(admin.ModelAdmin):
    list_display = ("name", "client", "type", "installed_date", "monitoring_url")
    list_filter = ("type",)
    search_fields = ("name", "client__name", "description")
    readonly_fields = ("credentials_encrypted",)
