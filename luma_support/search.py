"""Mixed-entity quick-search for the Cmd-K command palette.

Returns up to ~5 hits per entity type (tickets, clients, articles),
scoped to the caller's permissions. Each hit ships ``{type, label,
hint, url}`` so the front-end can render a uniform list without
caring which model produced the row.
"""
from __future__ import annotations

from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def search(request):
    from clients.models import Client
    from knowledge.models import Article
    from tickets.models import Ticket

    q = (request.query_params.get("q") or "").strip()
    if len(q) < 2:
        return Response({"results": []})

    user = request.user
    can_view_all = bool(getattr(user, "can_view_all", False))
    client_scope = getattr(user, "client_id", None)
    results = []

    # Tickets — title or #N
    t_qs = Ticket.objects.select_related("client")
    if not can_view_all:
        t_qs = t_qs.filter(client_id=client_scope) if client_scope else t_qs.none()
    if q.lstrip("#").isdigit():
        t_qs_id = t_qs.filter(pk=int(q.lstrip("#")))
    else:
        t_qs_id = t_qs.none()
    t_qs = (t_qs_id | t_qs.filter(subject__icontains=q)).distinct()[:5]
    for t in t_qs:
        results.append(
            {
                "type": "ticket",
                "label": f"#{t.pk} {t.subject}",
                "hint": t.client.name,
                "url": f"/tickets/{t.pk}/",
            }
        )

    # Clients
    if can_view_all:
        c_qs = Client.objects.filter(
            Q(name__icontains=q) | Q(company__icontains=q) | Q(email__icontains=q)
        )[:5]
        for c in c_qs:
            results.append(
                {
                    "type": "client",
                    "label": c.name,
                    "hint": c.company or c.email or "",
                    "url": f"/clients/{c.pk}/",
                }
            )

    # KB articles — visibility-scoped via the existing helper.
    if can_view_all:
        a_qs = Article.objects.filter(
            Q(title__icontains=q) | Q(content__icontains=q)
        )[:5]
    elif client_scope:
        client = Client.objects.filter(pk=client_scope).first()
        a_qs = (
            Article.objects.for_client(client).filter(
                Q(title__icontains=q) | Q(content__icontains=q)
            )[:5]
            if client else Article.objects.none()
        )
    else:
        a_qs = Article.objects.none()
    for a in a_qs:
        results.append(
            {
                "type": "kb",
                "label": a.title,
                "hint": a.get_category_display(),
                "url": f"/kb/{a.slug}/",
            }
        )

    return Response({"results": results})
