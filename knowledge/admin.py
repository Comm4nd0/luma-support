from django.contrib import admin

from .models import Article, ArticleAsset, ArticleRevision, KbSearchLog


@admin.register(ArticleRevision)
class ArticleRevisionAdmin(admin.ModelAdmin):
    list_display = ("article", "edited_by", "edited_at")
    list_filter = ("edited_at",)
    search_fields = ("article__title", "content")
    readonly_fields = ("article", "title", "content", "edited_by", "edited_at")


@admin.register(ArticleAsset)
class ArticleAssetAdmin(admin.ModelAdmin):
    list_display = ("article", "filename", "uploaded_by", "uploaded_at")
    search_fields = ("article__title", "filename")
    readonly_fields = ("uploaded_at",)


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "visibility", "published_at", "updated_at")
    list_filter = ("category", "visibility")
    search_fields = ("title", "content")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("allowed_clients",)


@admin.register(KbSearchLog)
class KbSearchLogAdmin(admin.ModelAdmin):
    list_display = ("query", "results_count", "source", "user", "created_at")
    list_filter = ("source", "results_count")
    search_fields = ("query",)
    readonly_fields = ("query", "user", "results_count", "source", "created_at")
