from django.contrib import admin

from .models import Article, KbSearchLog


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "client_visible", "published_at", "updated_at")
    list_filter = ("category", "client_visible")
    search_fields = ("title", "content")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(KbSearchLog)
class KbSearchLogAdmin(admin.ModelAdmin):
    list_display = ("query", "results_count", "source", "user", "created_at")
    list_filter = ("source", "results_count")
    search_fields = ("query",)
    readonly_fields = ("query", "user", "results_count", "source", "created_at")
