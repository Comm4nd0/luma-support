"""DRF API + portal OAuth views for Luma's social accounts.

API surface (staff-only, mounted under `/api/v1/social/`):
- `GET /accounts/` — connected accounts with stats
- `GET /inbox/` — paginated inbox queue (filter via `?status=open|...`)
- `POST /inbox/{id}/dismiss/`
- `POST /inbox/{id}/convert-to-ticket/` — optional body `{"client_id": N}`

Portal (under `/portal/social/`):
- `GET /` management page
- `GET /connect/{platform}/` — kick off OAuth
- `GET /callback/{platform}/` — provider returns here
- `POST /disconnect/{id}/` — remove a connection (audit-logged)
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.views import View
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from audit import log as audit_log
from clients.models import Client

from .models import InboxStatus, Platform, SocialAccount, SocialInboxItem
from .oauth import (
    authorize_url,
    exchange_code_linkedin,
    exchange_code_meta,
    sign_state,
    verify_state,
)
from .serializers import SocialAccountSerializer, SocialInboxItemSerializer

logger = logging.getLogger(__name__)


class IsStaff(permissions.BasePermission):
    """Engineer + admin only. Clients never touch this surface."""

    def has_permission(self, request, view) -> bool:
        u = request.user
        return bool(u and u.is_authenticated and getattr(u, "can_view_all", False))


class SocialAccountViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SocialAccountSerializer
    permission_classes = [IsStaff]
    queryset = SocialAccount.objects.all()


class SocialInboxItemViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SocialInboxItemSerializer
    permission_classes = [IsStaff]

    def get_queryset(self):
        qs = SocialInboxItem.objects.select_related("account", "converted_ticket")
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    @action(detail=True, methods=["post"], url_path="dismiss")
    def dismiss(self, request, pk=None):
        item = self.get_object()
        if item.status == InboxStatus.OPEN:
            item.status = InboxStatus.DISMISSED
            item.save(update_fields=["status"])
            audit_log("social.inbox_dismiss", request=request, target=item)
        return Response(self.get_serializer(item).data)

    @action(detail=True, methods=["post"], url_path="convert-to-ticket")
    def convert_to_ticket(self, request, pk=None):
        from .inbound import convert_inbox_item_to_ticket

        item = self.get_object()
        client_id = request.data.get("client_id")
        if client_id is not None:
            try:
                client_id = int(client_id)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "client_id must be an integer."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not Client.objects.filter(pk=client_id).exists():
                return Response(
                    {"detail": "Unknown client_id."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        ticket = convert_inbox_item_to_ticket(
            item, actor=request.user, client_id=client_id
        )
        audit_log(
            "social.inbox_convert",
            request=request,
            target=item,
            ticket_id=ticket.pk,
        )
        return Response(
            {
                **self.get_serializer(item).data,
                "ticket_id": ticket.pk,
            }
        )


# ---------------------------------------------------------------------
# Portal OAuth (admin only — token storage is sensitive)
# ---------------------------------------------------------------------


def _platform_param(value: str) -> str:
    """Normalise the URL slug into a `Platform` value. Raises on unknown."""
    if value in Platform.values:
        return value
    if value == "meta":
        # The Meta callback handles both FB Page + IG Business in one go.
        return value
    raise ValueError(f"unsupported platform slug: {value}")


class SocialSettingsView(View):
    template_name = "portal/social/connected.html"

    def get(self, request):
        if not getattr(request.user, "can_view_all", False):
            return redirect("portal:dashboard")
        accounts = SocialAccount.objects.all()
        configured = {
            Platform.LINKEDIN_PAGE: bool(settings.LINKEDIN_CLIENT_ID),
            Platform.FACEBOOK_PAGE: bool(settings.META_APP_ID),
            Platform.INSTAGRAM_BUSINESS: bool(settings.META_APP_ID),
        }
        return TemplateResponse(
            request,
            self.template_name,
            {
                "accounts": accounts,
                "configured": configured,
                "active": "social",
            },
        )


class SocialInboxView(View):
    """Server-rendered social inbox triage — parity with the mobile Social
    inbox screen.

    Lists inbox items (open by default, filterable by status) and lets staff
    dismiss one or convert it to a ticket. Reuses the same status transition
    + ``convert_inbox_item_to_ticket`` helper + audit events as the DRF
    ``/api/v1/social/inbox/`` endpoints, so both front-ends behave identically.
    """

    template_name = "portal/social/inbox.html"

    def get(self, request):
        if not getattr(request.user, "can_view_all", False):
            return redirect("portal:dashboard")
        status_filter = request.GET.get("status", InboxStatus.OPEN)
        qs = SocialInboxItem.objects.select_related("account", "converted_ticket")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return TemplateResponse(
            request,
            self.template_name,
            {
                "items": qs[:100],
                "status_filter": status_filter,
                "statuses": InboxStatus.choices,
                "open_count": SocialInboxItem.objects.filter(
                    status=InboxStatus.OPEN
                ).count(),
                "active": "social",
            },
        )

    def post(self, request):
        if not getattr(request.user, "can_view_all", False):
            return redirect("portal:dashboard")
        item = get_object_or_404(
            SocialInboxItem, pk=request.POST.get("item_id") or 0
        )
        action_name = request.POST.get("action")
        if action_name == "dismiss":
            if item.status == InboxStatus.OPEN:
                item.status = InboxStatus.DISMISSED
                item.save(update_fields=["status"])
                audit_log("social.inbox_dismiss", request=request, target=item)
            messages.success(request, "Dismissed.")
        elif action_name == "convert":
            from .inbound import convert_inbox_item_to_ticket

            ticket = convert_inbox_item_to_ticket(item, actor=request.user)
            audit_log(
                "social.inbox_convert",
                request=request,
                target=item,
                ticket_id=ticket.pk,
            )
            messages.success(request, f"Converted to ticket #{ticket.pk}.")
        return redirect("portal:social_inbox")


class SocialConnectView(View):
    """Kick off OAuth: sign state and redirect to the provider."""

    def get(self, request, platform):
        if not getattr(request.user, "can_view_all", False):
            return redirect("portal:dashboard")
        try:
            slug = _platform_param(platform)
        except ValueError:
            return HttpResponseBadRequest("Unsupported platform.")
        # FB and IG share an OAuth flow; we route both under the "meta" slug.
        oauth_platform = (
            Platform.FACEBOOK_PAGE if slug == "meta" else slug
        )
        state = sign_state(request.user.pk, slug)
        request.session[f"social_oauth_state_{slug}"] = state
        audit_log(
            "social.connect_start", request=request, platform=slug
        )
        return redirect(authorize_url(oauth_platform, state))


class SocialCallbackView(View):
    """Provider redirects here with `?code=...&state=...`."""

    def get(self, request, platform):
        if not getattr(request.user, "can_view_all", False):
            return redirect("portal:dashboard")
        try:
            slug = _platform_param(platform)
        except ValueError:
            return HttpResponseBadRequest("Unsupported platform.")

        state = request.GET.get("state", "")
        expected = request.session.pop(f"social_oauth_state_{slug}", None)
        if not state or state != expected or not verify_state(
            state, request.user.pk, slug
        ):
            return HttpResponseBadRequest("Invalid OAuth state.")
        code = request.GET.get("code", "")
        if not code:
            return HttpResponseBadRequest("Missing authorization code.")

        if slug == Platform.LINKEDIN_PAGE:
            _ingest_linkedin(request, code)
        elif slug == "meta":
            _ingest_meta(request, code)
        else:
            return HttpResponseBadRequest("Unsupported platform.")
        return redirect("portal:social_settings")


class SocialDisconnectView(View):
    def post(self, request, pk):
        if not getattr(request.user, "can_view_all", False):
            return redirect("portal:dashboard")
        account = get_object_or_404(SocialAccount, pk=pk)
        audit_log(
            "social.disconnect",
            request=request,
            target=account,
            platform=account.platform,
            external_id=account.external_id,
        )
        account.delete()
        messages.success(request, "Disconnected.")
        return redirect("portal:social_settings")


def _ingest_linkedin(request, code: str) -> None:
    try:
        payload = exchange_code_linkedin(code)
    except Exception:
        logger.exception("LinkedIn OAuth exchange failed")
        messages.error(request, "LinkedIn returned an error during connect.")
        return
    pages = payload.get("pages") or []
    if not pages:
        messages.error(
            request, "No LinkedIn Pages found for this account."
        )
        return
    for page in pages:
        account, _ = SocialAccount.objects.update_or_create(
            platform=Platform.LINKEDIN_PAGE,
            external_id=page["external_id"],
            defaults={
                "display_name": page.get("display_name", ""),
                "avatar_url": page.get("avatar_url", ""),
                "scopes": payload.get("scope", ""),
                "token_expires_at": payload.get("expires_at"),
                "connected_by": request.user,
            },
        )
        account.set_access_token(payload["access_token"])
        account.set_refresh_token(payload.get("refresh_token") or "")
        account.save()
        audit_log(
            "social.connect",
            request=request,
            target=account,
            platform=account.platform,
        )
    messages.success(request, f"LinkedIn connected ({len(pages)} page(s)).")


def _ingest_meta(request, code: str) -> None:
    try:
        payload = exchange_code_meta(code)
    except Exception:
        logger.exception("Meta OAuth exchange failed")
        messages.error(request, "Meta returned an error during connect.")
        return
    pages = payload.get("pages") or []
    if not pages:
        messages.error(request, "No Facebook Pages found for this account.")
        return
    connected = 0
    for page in pages:
        fb_account, _ = SocialAccount.objects.update_or_create(
            platform=Platform.FACEBOOK_PAGE,
            external_id=page["page_id"],
            defaults={
                "display_name": page.get("page_name", ""),
                "avatar_url": page.get("page_avatar", ""),
                "scopes": settings.META_SCOPES,
                "token_expires_at": None,  # Page tokens are long-lived.
                "connected_by": request.user,
            },
        )
        fb_account.set_access_token(page.get("page_token") or "")
        fb_account.save()
        audit_log(
            "social.connect",
            request=request,
            target=fb_account,
            platform=fb_account.platform,
        )
        connected += 1

        ig_id = page.get("ig_business_id")
        if ig_id:
            ig_account, _ = SocialAccount.objects.update_or_create(
                platform=Platform.INSTAGRAM_BUSINESS,
                external_id=ig_id,
                defaults={
                    "display_name": page.get("ig_username", ""),
                    "avatar_url": page.get("ig_avatar", ""),
                    "scopes": settings.META_SCOPES,
                    "token_expires_at": None,
                    "connected_by": request.user,
                },
            )
            ig_account.set_access_token(page.get("page_token") or "")
            ig_account.save()
            audit_log(
                "social.connect",
                request=request,
                target=ig_account,
                platform=ig_account.platform,
            )
            connected += 1
    messages.success(request, f"Meta connected ({connected} account(s)).")
