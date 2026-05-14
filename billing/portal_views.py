"""Admin-only portal pages for invoices and Xero settings."""
from __future__ import annotations

from django import forms
from django.contrib import messages
from django.db import transaction
from django.forms import inlineformset_factory
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView, ListView, View
from django.views.generic.edit import CreateView, UpdateView

from clients.models import Client

from .models import Invoice, InvoiceLine
from .permissions import AdminPortalMixin
from .services import generate_time_invoice


class InvoiceListView(AdminPortalMixin, ListView):
    model = Invoice
    template_name = "portal/billing/invoice_list.html"
    paginate_by = 50
    context_object_name = "invoices"

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

        from .models import XeroConnection

        try:
            conn = XeroConnection.objects.get(pk=1)
        except XeroConnection.DoesNotExist:
            conn = None
        return TemplateResponse(
            request,
            self.template_name,
            {"active": "billing", "connection": conn},
        )
