from rest_framework import serializers

from .models import Article


class ArticleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Article
        fields = (
            "id",
            "title",
            "slug",
            "content",
            "category",
            "client_visible",
            "published_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("slug", "created_at", "updated_at")
