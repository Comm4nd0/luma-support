from django.contrib import admin

from .models import FeatureFlag


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ("name", "enabled", "percentage", "updated_at")
    list_filter = ("enabled",)
    search_fields = ("name", "description")
    filter_horizontal = ("allowed_users",)
