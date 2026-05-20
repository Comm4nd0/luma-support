"""Public NPS submission view.

Tokenised, single-use — same shape as `tickets.CsatResponse`'s
submission page. On a Promoter (9-10) response the thank-you page
shows a "share your link" CTA tied to the client's referral code,
closing the loop between satisfaction and acquisition.
"""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.views import View

from .models import NpsResponse, ReferralCode


class NpsSubmitView(View):
    form_template = "portal/nps_form.html"
    thanks_template = "portal/nps_thanks.html"

    def get(self, request, token):
        resp = get_object_or_404(NpsResponse, token=token)
        if resp.score is not None:
            return self._thanks(request, resp, already=True)
        return TemplateResponse(request, self.form_template, {"resp": resp})

    def post(self, request, token):
        resp = get_object_or_404(NpsResponse, token=token)
        if resp.score is not None:
            return self._thanks(request, resp, already=True)
        try:
            score = int(request.POST.get("score") or -1)
        except (TypeError, ValueError):
            score = -1
        if not 0 <= score <= 10:
            return TemplateResponse(
                request,
                self.form_template,
                {"resp": resp, "error": "Please pick a score from 0 to 10."},
            )
        resp.score = score
        resp.comment = (request.POST.get("comment") or "").strip()
        resp.responded_at = timezone.now()
        resp.save(update_fields=["score", "comment", "responded_at"])
        return self._thanks(request, resp, already=False)

    @staticmethod
    def _thanks(request, resp, already):
        share_link = None
        if resp.category == "promoter":
            code = ReferralCode.for_client(resp.client)
            share_link = request.build_absolute_uri(
                reverse("portal:referral_redirect", args=[code.code])
            )
        return TemplateResponse(
            request,
            NpsSubmitView.thanks_template,
            {
                "resp": resp,
                "already": already,
                "share_link": share_link,
            },
        )
