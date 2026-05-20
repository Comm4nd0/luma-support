"""Public, unauthenticated lead-capture page.

Visitors who land at `/contact/` see a simple form. Submitting creates a
`Lead(source=WEBSITE)`. Add `?ref=<code>` and we tag the source as
REFERRAL — Phase A3 will then resolve `<code>` to a referring Client
via `clients.ReferralCode`; until then we just keep the raw code on
`source_detail` so the credit is attributable retroactively.

Spam defences:
- Honeypot input — bots populate `website`, real users leave it empty.
- IP cooldown via Django's cache: `_COOLDOWN_SECONDS` between posts
  from the same address.

The view stays a plain Django `View` (not DRF) because most embeds
will be a server-rendered form on the marketing site or a copy of the
HTML. CSRF protection is enabled — operators embedding cross-origin
need to add their host to `CSRF_TRUSTED_ORIGINS`.
"""
from __future__ import annotations

from django.core.cache import cache
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse
from django.views import View

from .models import Lead, LeadSource


_HONEYPOT_FIELD = "website"
_COOLDOWN_SECONDS = 60


def _client_ip(request: HttpRequest) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or "unknown"


class ContactFormView(View):
    form_template = "portal/leads/contact.html"
    thanks_template = "portal/leads/contact_thanks.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        return self._render_form(request, {})

    def post(self, request: HttpRequest) -> HttpResponse:
        # Honeypot: silently pretend success so bots don't retry.
        if (request.POST.get(_HONEYPOT_FIELD) or "").strip():
            return self._render_thanks(request)

        cache_key = f"contact_form_ip:{_client_ip(request)}"
        if cache.get(cache_key):
            return self._render_form(
                request,
                {
                    "error": "Please slow down and try again in a minute.",
                    "form": _form_state(request),
                },
                status=429,
            )

        name = (request.POST.get("name") or "").strip()
        email = (request.POST.get("email") or "").strip()
        phone = (request.POST.get("phone") or "").strip()

        if not name or not (email or phone):
            return self._render_form(
                request,
                {
                    "error": "Please tell us your name and either an email or phone.",
                    "form": _form_state(request),
                },
            )

        company = (request.POST.get("company") or "").strip()
        message = (request.POST.get("message") or "").strip()

        ref_code = (
            request.GET.get("ref")
            or request.POST.get("ref")
            or ""
        ).strip()
        referring_client = None
        if ref_code:
            source = LeadSource.REFERRAL
            source_detail = f"ref={ref_code[:64]}"
            # Resolve the code to a real Client via ReferralCode so credit
            # can be applied automatically when the lead converts.
            try:
                from clients.models import ReferralCode

                rc = ReferralCode.objects.filter(code=ref_code).first()
                if rc is not None:
                    referring_client = rc.client
            except Exception:
                pass
        else:
            source = LeadSource.WEBSITE
            source_detail = ""

        Lead.objects.create(
            name=name[:200],
            email=email[:200],
            phone=phone[:32],
            company=company[:200],
            interest=message[:4000],
            source=source,
            source_detail=source_detail,
            referring_client=referring_client,
        )

        # Cooldown stamped only after a successful submission so a bot
        # tripping the honeypot doesn't lock a real visitor out.
        cache.set(cache_key, "1", _COOLDOWN_SECONDS)

        return self._render_thanks(request)

    def _render_form(
        self, request: HttpRequest, context: dict, *, status: int = 200
    ) -> HttpResponse:
        ctx = {"ref": request.GET.get("ref", ""), **context}
        return TemplateResponse(request, self.form_template, ctx, status=status)

    def _render_thanks(self, request: HttpRequest) -> HttpResponse:
        return TemplateResponse(request, self.thanks_template, {})


def _form_state(request: HttpRequest) -> dict:
    return {
        "name": request.POST.get("name", ""),
        "email": request.POST.get("email", ""),
        "phone": request.POST.get("phone", ""),
        "company": request.POST.get("company", ""),
        "message": request.POST.get("message", ""),
    }
