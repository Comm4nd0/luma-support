from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "type", "title", "read", "push_sent", "created_at")
    list_filter = ("type", "read", "push_sent")
    search_fields = ("title", "body", "user__email")
