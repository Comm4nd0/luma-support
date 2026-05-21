from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Article, KbSearchLog
from .serializers import ArticleSerializer


def _log_search(query: str, *, user, results_count: int, source: str) -> None:
    """Best-effort search log — never raises so the user request is safe."""
    if not query:
        return
    try:
        KbSearchLog.objects.create(
            query=query[:500],
            user=user if getattr(user, "is_authenticated", False) else None,
            results_count=results_count,
            source=source,
        )
    except Exception:
        # Audit-style: never break the caller on a logging failure.
        pass


class ArticleViewSet(viewsets.ModelViewSet):
    serializer_class = ArticleSerializer
    filterset_fields = ["category", "client_visible"]
    search_fields = ["title", "content"]
    lookup_field = "slug"

    def get_queryset(self):
        # Clients only see published articles scoped to their own
        # client (all_clients OR specific_clients with them in the
        # allowlist). Staff see everything.
        user = self.request.user
        if user.is_authenticated and getattr(user, "is_client", False):
            client = getattr(user, "client", None)
            if client is None:
                return Article.objects.none()
            return Article.objects.for_client(client)
        return Article.objects.all()

    @action(detail=False, methods=["get"])
    def search(self, request):
        q = request.query_params.get("q", "").strip()
        qs = self.get_queryset()
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(content__icontains=q))
        results = list(qs[:50])
        _log_search(q, user=request.user, results_count=len(results), source="search")
        return Response(ArticleSerializer(results, many=True).data)

    @action(detail=False, methods=["post"])
    def suggest(self, request):
        """Return up to 3 KB articles likely to help with the supplied
        ticket draft. Body: `{"subject": "...", "description": "..."}`.
        Falls back to keyword search when ANTHROPIC_API_KEY is empty.
        """
        from .ai import suggest_articles

        subject = (request.data.get("subject") or "").strip()
        description = (request.data.get("description") or "").strip()
        client_visible_only = not getattr(
            request.user, "can_view_all", False
        )
        suggestions = suggest_articles(
            subject, description, client_visible_only=client_visible_only
        )
        _log_search(
            subject,
            user=request.user,
            results_count=len(suggestions),
            source="suggest",
        )
        return Response(
            {
                "suggestions": [
                    {
                        "slug": s.article.slug,
                        "title": s.article.title,
                        "snippet": s.snippet,
                        "reason": s.reason,
                    }
                    for s in suggestions
                ]
            }
        )
