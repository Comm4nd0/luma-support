"""Portal views for referral codes.

- `/r/<code>/` public redirect to the contact form pre-filled with the
  code so a client can share their link in one click.
- `/portal/refer/` client-facing dashboard: their code, share link, the
  leads they've sent in, current credit balance.
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.views import View

from .models import Client, ReferralCode


class ReferralRedirectView(View):
    """Public: turn `/r/<code>/` into a tidy contact-form URL."""

    def get(self, request, code):
        # Don't 404 unknown codes — let the form still capture the lead
        # with the raw code stored on source_detail; staff can sort it.
        url = f"{reverse('portal:contact')}?ref={code}"
        return redirect(url)


class ReferralDashboardView(LoginRequiredMixin, View):
    """Client-facing page showing their referral code, share link, and balance."""

    template = "portal/leads/refer.html"

    def get(self, request):
        client = _client_for_user(request.user)
        if client is None:
            return TemplateResponse(
                request, self.template, {"client": None, "active": "refer"}
            )
        code = ReferralCode.for_client(client)
        share_link = (
            f"{request.scheme}://{request.get_host()}"
            f"{reverse('portal:referral_redirect', args=[code.code])}"
        )
        referrals = list(
            client.referrals.select_related("converted_client").order_by(
                "-created_at"
            )
        )
        credit = getattr(settings, "REFERRAL_CREDIT_GBP", "25")
        # Ready-to-share copy for email + WhatsApp deep links so the
        # client doesn't have to type a thing.
        share_subject = (
            f"{client.name} just recommended Luma Tech Solutions"
        )
        share_body = (
            f"Hey — I use Luma Tech Solutions for my tech (UniFi / "
            f"smart home / web / CCTV) and they handle everything. "
            f"They give us both £{credit} credit if you sign up:\n\n"
            f"{share_link}"
        )
        return TemplateResponse(
            request,
            self.template,
            {
                "client": client,
                "code": code,
                "share_link": share_link,
                "referrals": referrals,
                "credit": credit,
                "refer_share_subject": share_subject,
                "refer_share_body": share_body,
                "active": "refer",
            },
        )


def _client_for_user(user) -> Client | None:
    """Return the Client a user is acting on behalf of.

    Client users have `user.client` set. Staff don't — they get a
    helpful "pick a client" prompt instead of a referral page.
    """
    if not user.is_authenticated:
        return None
    return getattr(user, "client", None)
