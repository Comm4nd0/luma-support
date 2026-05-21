"""Admin-only portal pages for invoices and Xero settings."""
from __future__ import annotations

import secrets
from datetime import timedelta

from django import forms
from django.contrib import messages
from django.db import transaction
from django.forms import inlineformset_factory
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import DetailView, ListView, View
from django.views.generic.edit import CreateView, UpdateView

from clients.models import Client
from luma_support.exports import CsvExportMixin

from .models import Invoice, InvoiceLine, XeroConnection
from .permissions import AdminPortalMixin
from .services import generate_time_invoice


class RevenueDashboardView(AdminPortalMixin, View):
    """Admin-only revenue overview — current MRR, ARR, churn, 12-month chart."""

    template_name = "portal/revenue_dashboard.html"

    def get(self, request):
        from decimal import Decimal

        from django.template.response import TemplateResponse

        from . import metrics

        history = metrics.mrr_history(months=12)
        mrr_now = metrics.current_mrr()
        max_mrr = max((b.mrr for b in history), default=Decimal("0"))
        return TemplateResponse(
            request,
            self.template_name,
            {
                "active": "revenue",
                "current_mrr": mrr_now,
                "arr": metrics.arr(),
                "mrr_by_tier": metrics.mrr_by_tier(),
                "history": history,
                "max_mrr": max_mrr if max_mrr > 0 else Decimal("1"),
                "gross_churn": metrics.gross_churn_rate(window_days=90),
                "nrr": metrics.net_revenue_retention(months=12),
            },
        )


class InvoiceListView(CsvExportMixin, AdminPortalMixin, ListView):
    model = Invoice
    template_name = "portal/billing/invoice_list.html"
    paginate_by = 50
    context_object_name = "invoices"
    csv_filename = "invoices"
    csv_columns = (
        ("id", "pk"),
        ("kind", "get_kind_display"),
        ("client", "client.name"),
        ("status", "get_status_display"),
        ("subtotal", "subtotal"),
        ("tax", "tax"),
        ("total", "total"),
        ("currency", "currency"),
        ("due_date", "due_date"),
        ("created_at", "created_at"),
        ("paid_at", "paid_at"),
        ("xero_invoice_id", "xero_invoice_id"),
    )

    def get_queryset(self):
        return Invoice.objects.select_related("client").order_by("-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "billing"
        return ctx


class InvoiceDetailView(AdminPortalMixin, DetailView):
    model = Invoice
    template_name = "portal/billing/invoice_detail.html"
    context_object_name = "invoice"

    def get_queryset(self):
        return Invoice.objects.select_related("client").prefetch_related(
            "lines", "payments"
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "billing"
        return ctx


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ["client", "due_date", "currency", "notes"]
        widgets = {
            "client": forms.Select(attrs={"class": "form-input"}),
            "due_date": forms.DateInput(
                attrs={"class": "form-input", "type": "date"}
            ),
            "currency": forms.TextInput(attrs={"class": "form-input"}),
            "notes": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
        }


class InvoiceLineForm(forms.ModelForm):
    class Meta:
        model = InvoiceLine
        fields = ["description", "quantity", "unit_amount", "account_code", "tax_type"]
        widgets = {
            "description": forms.TextInput(attrs={"class": "form-input"}),
            "quantity": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.01", "min": "0"}
            ),
            "unit_amount": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.01", "min": "0"}
            ),
            "account_code": forms.TextInput(attrs={"class": "form-input"}),
            "tax_type": forms.TextInput(attrs={"class": "form-input"}),
        }


InvoiceLineFormSet = inlineformset_factory(
    Invoice,
    InvoiceLine,
    form=InvoiceLineForm,
    extra=3,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class InvoiceCreateView(AdminPortalMixin, CreateView):
    """One-off invoice create form with inline line items."""

    model = Invoice
    form_class = InvoiceForm
    template_name = "portal/billing/invoice_form.html"

    def get_initial(self):
        initial = super().get_initial()
        client_id = self.request.GET.get("client")
        if client_id:
            initial["client"] = client_id
        from django.conf import settings

        initial.setdefault("currency", settings.DEFAULT_CURRENCY)
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "billing"
        if self.request.method == "POST":
            ctx["lines"] = InvoiceLineFormSet(self.request.POST)
        else:
            ctx["lines"] = InvoiceLineFormSet()
        return ctx

    def form_valid(self, form):
        ctx = self.get_context_data()
        lines = ctx["lines"]
        if not lines.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        with transaction.atomic():
            form.instance.kind = Invoice.Kind.ONE_OFF
            form.instance.status = Invoice.Status.DRAFT
            form.instance.created_by = self.request.user
            self.object = form.save()
            lines.instance = self.object
            lines.save()
            self.object.recalculate_totals()
            self.object.save(
                update_fields=["subtotal", "tax", "total", "updated_at"]
            )
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("portal:invoice_detail", args=[self.object.pk])


class InvoiceUpdateView(AdminPortalMixin, UpdateView):
    """Edit a DRAFT invoice. Anything else is read-only."""

    model = Invoice
    form_class = InvoiceForm
    template_name = "portal/billing/invoice_form.html"

    def get_queryset(self):
        return Invoice.objects.filter(status=Invoice.Status.DRAFT)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "billing"
        if self.request.method == "POST":
            ctx["lines"] = InvoiceLineFormSet(self.request.POST, instance=self.object)
        else:
            ctx["lines"] = InvoiceLineFormSet(instance=self.object)
        return ctx

    def form_valid(self, form):
        ctx = self.get_context_data()
        lines = ctx["lines"]
        if not lines.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        with transaction.atomic():
            self.object = form.save()
            lines.save()
            self.object.recalculate_totals()
            self.object.save(
                update_fields=["subtotal", "tax", "total", "updated_at"]
            )
        return redirect(reverse("portal:invoice_detail", args=[self.object.pk]))


class ClientGenerateTimeInvoiceView(AdminPortalMixin, View):
    """Bundle unbilled time entries for a client into a new draft invoice."""

    def post(self, request, pk):
        client = get_object_or_404(Client, pk=pk)
        invoice = generate_time_invoice(client)
        if invoice is None:
            messages.info(request, "No unbilled time entries for this client.")
            return redirect("portal:client_detail", pk=client.pk)
        messages.success(
            request,
            f"Created draft invoice #{invoice.pk} for {len(invoice.lines.all())} ticket(s).",
        )
        return redirect("portal:invoice_detail", pk=invoice.pk)


# --- Xero settings ------------------------------------------------------


class XeroSettingsView(AdminPortalMixin, View):
    template_name = "portal/billing/xero_settings.html"

    def get(self, request):
        from django.template.response import TemplateResponse

        try:
            conn = XeroConnection.objects.get(pk=1)
        except XeroConnection.DoesNotExist:
            conn = None
        return TemplateResponse(
            request,
            self.template_name,
            {"active": "billing", "connection": conn},
        )


class XeroConnectView(AdminPortalMixin, View):
    """Kick off the OAuth flow — stash state in session and redirect to Xero."""

    def get(self, request):
        from audit import log as audit_log
        from .xero import oauth

        state = secrets.token_urlsafe(32)
        request.session["xero_oauth_state"] = state
        audit_log("xero.connect_start", request=request)
        return redirect(oauth.authorize_url(state))


class XeroOAuthCallbackView(AdminPortalMixin, View):
    def get(self, request):
        from .xero import oauth

        state = request.GET.get("state", "")
        code = request.GET.get("code", "")
        expected = request.session.pop("xero_oauth_state", None)
        if not expected or state != expected:
            return HttpResponseBadRequest("Invalid OAuth state.")
        if not code:
            return HttpResponseBadRequest("Missing authorization code.")

        tokens = oauth.exchange_code(code)
        connections = oauth.list_connections(tokens["access_token"])
        if not connections:
            messages.error(request, "Xero returned no connected organisations.")
            return redirect("portal:xero_settings")
        tenant_id = connections[0]["tenantId"]

        conn, _ = XeroConnection.objects.get_or_create(
            pk=1,
            defaults={
                "tenant_id": tenant_id,
                "access_token": tokens["access_token"],
                "expires_at": timezone.now()
                + timedelta(seconds=int(tokens["expires_in"])),
                "connected_by": request.user,
            },
        )
        conn.tenant_id = tenant_id
        conn.access_token = tokens["access_token"]
        conn.expires_at = timezone.now() + timedelta(
            seconds=int(tokens["expires_in"])
        )
        conn.connected_by = request.user
        conn.set_refresh_token(tokens["refresh_token"])
        conn.save()
        from audit import log as audit_log

        audit_log(
            "xero.connect",
            request=request,
            target=conn,
            tenant_id=tenant_id,
        )
        messages.success(request, "Xero connected.")
        return redirect("portal:xero_settings")


class XeroDisconnectView(AdminPortalMixin, View):
    def post(self, request):
        from audit import log as audit_log

        existing = XeroConnection.objects.first()
        if existing is not None:
            audit_log(
                "xero.disconnect",
                request=request,
                target=existing,
                tenant_id=existing.tenant_id,
            )
        XeroConnection.objects.all().delete()
        messages.success(request, "Xero disconnected.")
        return redirect("portal:xero_settings")


class InvoiceSendView(AdminPortalMixin, View):
    """Enqueue a push of the invoice to Xero."""

    def post(self, request, pk):
        from audit import log as audit_log
        from .tasks import push_invoice_to_xero

        invoice = get_object_or_404(Invoice, pk=pk)
        if invoice.xero_invoice_id:
            messages.info(request, "Already pushed to Xero.")
            return redirect("portal:invoice_detail", pk=pk)
        if not XeroConnection.objects.exists():
            messages.error(request, "Connect Xero first.")
            return redirect("portal:xero_settings")
        push_invoice_to_xero.delay(invoice.pk, "AUTHORISED")
        audit_log(
            "invoice.send_to_xero",
            request=request,
            target=invoice,
            total=str(invoice.total),
            currency=invoice.currency,
        )
        messages.success(request, "Push to Xero queued.")
        return redirect("portal:invoice_detail", pk=pk)
