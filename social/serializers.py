"""DRF serializers — token fields are never serialised."""
from rest_framework import serializers

from .models import SocialAccount, SocialInboxItem


class SocialAccountSerializer(serializers.ModelSerializer):
    platform_display = serializers.CharField(
        source="get_platform_display", read_only=True
    )
    health_display = serializers.CharField(
        source="get_health_status_display", read_only=True
    )
    followers_delta_7d = serializers.IntegerField(read_only=True)
    days_since_last_post = serializers.IntegerField(read_only=True)

    class Meta:
        model = SocialAccount
        fields = [
            "id",
            "platform",
            "platform_display",
            "external_id",
            "display_name",
            "avatar_url",
            "health_status",
            "health_display",
            "last_checked_at",
            "last_error",
            "followers",
            "followers_7d_ago",
            "followers_delta_7d",
            "last_post_at",
            "days_since_last_post",
            "kpis_json",
            "connected_at",
        ]
        read_only_fields = fields


class SocialInboxItemSerializer(serializers.ModelSerializer):
    account_platform = serializers.CharField(source="account.platform", read_only=True)
    account_display = serializers.CharField(
        source="account.display_name", read_only=True
    )
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = SocialInboxItem
        fields = [
            "id",
            "account",
            "account_platform",
            "account_display",
            "kind",
            "kind_display",
            "external_id",
            "author_handle",
            "author_display",
            "preview",
            "permalink",
            "received_at",
            "fetched_at",
            "status",
            "converted_ticket",
        ]
        read_only_fields = fields
