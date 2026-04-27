from django.contrib import admin

from .models import Article


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "client_visible", "published_at", "updated_at")
    list_filter = ("category", "client_visible")
    search_fields = ("title", "content")
    prepopulated_fields = {"slug": ("title",)}
