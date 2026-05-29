"""Server-rendered quote pages — staff CRUD plus the public accept link."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView

from clients.models import Client
from leads.models import Lead

from .models import Quote, QuoteLine, QuoteStatus
from .services import accept_quote, reject_quote, send_quote


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    raise_exception = False

    def test_func(self) -> bool:
        u = self.request.user
        return bool(u.is_authenticated and getattr(u, "can_view_all", False))

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        return redirect("portal:dashboard")


class QuoteForm(forms.ModelForm):
    class Meta:
        model = Quote
        fields = ["lead", "client", "valid_until", "tax", "currency", "notes"]
        widgets = {
            "lead": forms.Select(attrs={"class": "form-input"}),
            "client": forms.Select(attrs={"class": "form-input"}),
            "valid_until": forms.DateInput(
                attrs={"class": "form-input", "type": "date"}
            ),
            "tax": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.01", "min": "0"}
            ),
            "currency": forms.TextInput(attrs={"class": "form-input"}),
            "notes": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["lead"].queryset = Lead.objects.order_by("-created_at")
        self.fields["client"].queryset = Client.objects.order_by("name")
        self.fields["lead"].required = False
        self.fields["client"].required = False

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("lead") and not cleaned.get("client"):
            raise forms.ValidationError(
                "A quote must be raised against either a lead or a client."
            )
        return cleaned


# -----------------------------------------------------------------
# Staff-facing pages
# -----------------------------------------------------------------


class QuoteListView(StaffRequiredMixin, ListView):
    model = Quote
    template_name = "portal/quotes/list.html"
    paginate_by = 50
    context_object_name = "quotes"

    def get_queryset(self):
        qs = Quote.objects.select_related("client", "lead", "converted_invoice")
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs.order_by("-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "quotes"
        ctx["statuses"] = QuoteStatus.choices
        ctx["filters"] = {"status": self.request.GET.get("status", "")}
        return ctx


class QuoteCreateView(StaffRequiredMixin, View):
    template = "portal/quotes/form.html"

    def get(self, request):
        initial = {}
        lead_id = request.GET.get("lead")
        if lead_id:
            initial["lead"] = lead_id
        client_id = request.GET.get("client")
        if client_id:
            initial["client"] = client_id
        return TemplateResponse(
            request,
            self.template,
            {
                "form": QuoteForm(initial=initial),
                "lines": [],
                "active": "quotes",
            },
        )

    def post(self, request):
        form = QuoteForm(request.POST)
        lines = _parse_line_rows(request.POST)
        if not form.is_valid() or not lines:
            return TemplateResponse(
                request,
                self.template,
                {
                    "form": form,
                    "lines": lines,
                    "active": "quotes",
                    "error": (
                        None if form.is_valid()
                        else "Fix the highlighted fields."
                    ) or ("Add at least one line." if not lines else None),
                },
            )
        quote = form.save(commit=False)
        quote.created_by = request.user
        quote.save()
        for ln in lines:
            QuoteLine.objects.create(quote=quote, **ln)
        quote.recalculate_totals()
        quote.save(update_fields=["subtotal", "total"])
        messages.success(request, f"Quote {quote.number} drafted.")
        return redirect("portal:quote_detail", pk=quote.pk)


class QuoteUpdateView(StaffRequiredMixin, View):
    template = "portal/quotes/form.html"

    def get(self, request, pk):
        quote = get_object_or_404(Quote, pk=pk)
        lines = [
            {
                "description": ln.description,
                "quantity": ln.quantity,
                "unit_amount": ln.unit_amount,
            }
            for ln in quote.lines.all()
        ]
        return TemplateResponse(
            request,
            self.template,
            {
                "form": QuoteForm(instance=quote),
                "lines": lines,
                "quote": quote,
                "active": "quotes",
            },
        )

    def post(self, request, pk):
        quote = get_object_or_404(Quote, pk=pk)
        if quote.status not in (QuoteStatus.DRAFT, QuoteStatus.SENT):
            messages.error(
                request,
                "Accepted, rejected or expired quotes can't be edited.",
            )
            return redirect("portal:quote_detail", pk=quote.pk)
        form = QuoteForm(request.POST, instance=quote)
        lines = _parse_line_rows(request.POST)
        if not form.is_valid() or not lines:
            return TemplateResponse(
                request,
                self.template,
                {
                    "form": form,
                    "lines": lines,
                    "quote": quote,
                    "active": "quotes",
                },
            )
        form.save()
        quote.lines.all().delete()
        for ln in lines:
            QuoteLine.objects.create(quote=quote, **ln)
        quote.recalculate_totals()
        quote.save(update_fields=["subtotal", "total"])
        messages.success(request, f"Quote {quote.number} updated.")
        return redirect("portal:quote_detail", pk=quote.pk)


class QuoteDetailView(StaffRequiredMixin, DetailView):
    model = Quote
    template_name = "portal/quotes/detail.html"
    context_object_name = "quote"

    def get_queryset(self):
        return Quote.objects.select_related(
            "client", "lead", "converted_invoice"
        ).prefetch_related("lines")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "quotes"
        ctx["accept_url"] = reverse(
            "portal:quote_public", args=[self.object.accept_token]
        )
        return ctx


class QuoteSendView(StaffRequiredMixin, View):
    def post(self, request, pk):
        quote = get_object_or_404(Quote, pk=pk)
        sent = send_quote(quote, by_user=request.user)
        if sent:
            messages.success(request, f"Quote {quote.number} emailed to {quote.recipient_email}.")
        else:
            messages.info(
                request,
                f"Quote {quote.number} marked sent — no recipient email on file.",
            )
        return redirect("portal:quote_detail", pk=quote.pk)


class QuotePrintView(StaffRequiredMixin, DetailView):
    """Print-friendly HTML — print-to-PDF from the browser."""

    model = Quote
    template_name = "portal/quotes/print.html"
    context_object_name = "quote"


# -----------------------------------------------------------------
# Public accept / reject (tokenised, no auth)
# -----------------------------------------------------------------


def _client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or ""


class QuotePublicView(View):
    template = "portal/quotes/accept.html"
    accepted_template = "portal/quotes/accepted.html"

    def get(self, request, token):
        quote = get_object_or_404(Quote, accept_token=token)
        if quote.status == QuoteStatus.ACCEPTED:
            return self._already(request, quote)
        return TemplateResponse(
            request,
            self.template,
            {"quote": quote, "expired": quote.is_expired},
        )

    def post(self, request, token):
        quote = get_object_or_404(Quote, accept_token=token)
        if quote.status == QuoteStatus.ACCEPTED:
            return self._already(request, quote)
        if quote.is_expired:
            return TemplateResponse(
                request,
                self.template,
                {"quote": quote, "expired": True},
                status=410,
            )

        action = request.POST.get("action") or "accept"
        if action == "reject":
            reject_quote(
                quote,
                reason=(request.POST.get("reason") or "")[:200],
            )
            return TemplateResponse(
                request,
                self.template,
                {"quote": quote, "rejected": True},
            )

        name = (request.POST.get("name") or "").strip()
        if not name:
            return TemplateResponse(
                request,
                self.template,
                {
                    "quote": quote,
                    "expired": quote.is_expired,
                    "error": "Please type your name to accept.",
                },
            )
        accept_quote(
            quote,
            accepted_by_name=name,
            accepted_ip=_client_ip(request),
        )
        return self._already(request, quote, fresh=True)

    @staticmethod
    def _already(request, quote, *, fresh: bool = False):
        return TemplateResponse(
            request,
            QuotePublicView.accepted_template,
            {"quote": quote, "fresh": fresh},
        )


# -----------------------------------------------------------------
# Line-row parsing helper
# -----------------------------------------------------------------


def _parse_line_rows(post) -> list[dict]:
    """Turn the repeated `line-description[]`, `line-quantity[]`,
    `line-unit_amount[]` posted fields into a list of dicts.

    Empty rows are silently skipped.
    """
    descriptions = post.getlist("line-description") or post.getlist(
        "line-description[]"
    )
    quantities = post.getlist("line-quantity") or post.getlist("line-quantity[]")
    units = post.getlist("line-unit_amount") or post.getlist("line-unit_amount[]")
    out: list[dict] = []
    for d, q, u in zip(descriptions, quantities, units, strict=False):
        d = (d or "").strip()
        if not d:
            continue
        try:
            qd = Decimal(q or "0")
            ud = Decimal(u or "0")
        except InvalidOperation:
            continue
        out.append({"description": d, "quantity": qd, "unit_amount": ud})
    return out
