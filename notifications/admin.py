from django.contrib import admin

from .models import DeviceToken, Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "type", "title", "read", "push_sent", "created_at")
    list_filter = ("type", "read", "push_sent")
    search_fields = ("title", "body", "user__email")


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "platform", "is_active", "app_version", "last_seen_at")
    list_filter = ("platform", "is_active")
    search_fields = ("token", "user__email")
