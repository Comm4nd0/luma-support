from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Article
from .serializers import ArticleSerializer


class ArticleViewSet(viewsets.ModelViewSet):
    serializer_class = ArticleSerializer
    filterset_fields = ["category", "client_visible"]
    search_fields = ["title", "content"]
    lookup_field = "slug"

    def get_queryset(self):
        # Clients only see published, client-visible articles.
        user = self.request.user
        if user.is_authenticated and getattr(user, "is_client", False):
            return Article.objects.visible_to_clients()
        return Article.objects.all()

    @action(detail=False, methods=["get"])
    def search(self, request):
        q = request.query_params.get("q", "").strip()
        qs = self.get_queryset()
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(content__icontains=q))
        return Response(ArticleSerializer(qs[:50], many=True).data)
