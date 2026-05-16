from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "target_repr", "ip")
    list_filter = ("action",)
    search_fields = ("action", "target_repr", "actor__email", "ip")
    readonly_fields = (
        "actor",
        "action",
        "target_ct",
        "target_id",
        "target_repr",
        "ip",
        "user_agent",
        "metadata",
        "created_at",
    )

    def has_add_permission(self, request):
        return False
