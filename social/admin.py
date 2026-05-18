from django.contrib import admin

from .models import SocialAccount, SocialInboxItem


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    list_display = (
        "platform",
        "display_name",
        "health_status",
        "followers",
        "last_post_at",
        "last_checked_at",
    )
    list_filter = ("platform", "health_status")
    search_fields = ("display_name", "external_id")
    readonly_fields = (
        "access_token_encrypted",
        "refresh_token_encrypted",
        "last_error",
        "last_checked_at",
        "connected_at",
        "created_at",
        "updated_at",
    )


@admin.register(SocialInboxItem)
class SocialInboxItemAdmin(admin.ModelAdmin):
    list_display = (
        "account",
        "kind",
        "author_handle",
        "received_at",
        "status",
    )
    list_filter = ("kind", "status", "account__platform")
    search_fields = ("author_handle", "preview", "external_id")
    readonly_fields = ("fetched_at",)
