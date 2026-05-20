"""Server-rendered portal pages for the lead pipeline (staff only)."""
from __future__ import annotations

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from audit import log as audit_log
from clients.models import Client

from .models import ActivityKind, Lead, LeadActivity, LeadStage


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    raise_exception = False

    def test_func(self) -> bool:
        u = self.request.user
        return bool(u.is_authenticated and getattr(u, "can_view_all", False))

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        return redirect("portal:dashboard")


class LeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = [
            "name",
            "company",
            "email",
            "phone",
            "customer_type",
            "source",
            "source_detail",
            "referring_client",
            "interest",
            "estimated_value",
            "stage",
            "next_action_at",
            "assigned_to",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input"}),
            "company": forms.TextInput(attrs={"class": "form-input"}),
            "email": forms.EmailInput(attrs={"class": "form-input"}),
            "phone": forms.TextInput(attrs={"class": "form-input"}),
            "customer_type": forms.Select(attrs={"class": "form-input"}),
            "source": forms.Select(attrs={"class": "form-input"}),
            "source_detail": forms.TextInput(attrs={"class": "form-input"}),
            "referring_client": forms.Select(attrs={"class": "form-input"}),
            "interest": forms.Textarea(attrs={"class": "form-input", "rows": 4}),
            "estimated_value": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.01", "min": "0"}
            ),
            "stage": forms.Select(attrs={"class": "form-input"}),
            "next_action_at": forms.DateTimeInput(
                attrs={"class": "form-input", "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "assigned_to": forms.Select(attrs={"class": "form-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        User = get_user_model()
        self.fields["assigned_to"].queryset = User.objects.filter(
            role__in=["admin", "engineer"], is_active=True
        ).order_by("email")
        self.fields["referring_client"].queryset = Client.objects.order_by("name")
        self.fields["next_action_at"].input_formats = ["%Y-%m-%dT%H:%M"]


class LeadListView(StaffRequiredMixin, ListView):
    model = Lead
    template_name = "portal/leads/list.html"
    paginate_by = 50
    context_object_name = "leads"

    def get_queryset(self):
        qs = Lead.objects.select_related(
            "assigned_to", "referring_client", "converted_client"
        )
        stage = self.request.GET.get("stage")
        source = self.request.GET.get("source")
        if stage:
            qs = qs.filter(stage=stage)
        if source:
            qs = qs.filter(source=source)
        return qs.order_by("stage", "next_action_at", "-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "leads"
        ctx["stages"] = LeadStage.choices
        ctx["sources"] = [
            (value, label)
            for value, label in Lead._meta.get_field("source").choices
        ]
        ctx["filters"] = {
            "stage": self.request.GET.get("stage", ""),
            "source": self.request.GET.get("source", ""),
        }
        # Stage counts for the summary strip at the top.
        from django.db.models import Count

        counts = dict(
            Lead.objects.values_list("stage").annotate(c=Count("id")).values_list(
                "stage", "c"
            )
        )
        ctx["stage_counts"] = [
            {
                "stage": value,
                "label": label,
                "count": counts.get(value, 0),
            }
            for value, label in LeadStage.choices
        ]
        return ctx


class LeadCreateView(StaffRequiredMixin, CreateView):
    model = Lead
    form_class = LeadForm
    template_name = "portal/leads/form.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        audit_log("lead.create", request=self.request, target=self.object)
        return response

    def get_success_url(self):
        return reverse("portal:lead_detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "leads"
        return ctx


class LeadUpdateView(StaffRequiredMixin, UpdateView):
    model = Lead
    form_class = LeadForm
    template_name = "portal/leads/form.html"

    def form_valid(self, form):
        prior_stage = Lead.objects.values_list("stage", flat=True).get(pk=self.object.pk)
        response = super().form_valid(form)
        if prior_stage != self.object.stage:
            LeadActivity.objects.create(
                lead=self.object,
                kind=ActivityKind.STAGE_CHANGE,
                body=f"{prior_stage} → {self.object.stage}",
                actor=self.request.user,
            )
            audit_log(
                "lead.stage_change",
                request=self.request,
                target=self.object,
                from_stage=prior_stage,
                to_stage=self.object.stage,
            )
        return response

    def get_success_url(self):
        return reverse("portal:lead_detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "leads"
        return ctx


class LeadDetailView(StaffRequiredMixin, DetailView):
    model = Lead
    template_name = "portal/leads/detail.html"
    context_object_name = "lead"

    def get_queryset(self):
        return Lead.objects.select_related(
            "assigned_to", "referring_client", "converted_client"
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "leads"
        ctx["activities"] = self.object.activities.select_related("actor")
        ctx["activity_kinds"] = ActivityKind.choices
        ctx["stages"] = LeadStage.choices
        return ctx


class LeadActivityCreateView(StaffRequiredMixin, View):
    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk)
        body = (request.POST.get("body") or "").strip()
        kind = request.POST.get("kind") or ActivityKind.NOTE
        valid_kinds = {value for value, _ in ActivityKind.choices}
        if not body:
            messages.error(request, "Activity body cannot be empty.")
        elif kind not in valid_kinds:
            messages.error(request, "Invalid activity kind.")
        else:
            LeadActivity.objects.create(
                lead=lead, kind=kind, body=body, actor=request.user
            )
            messages.success(request, "Activity logged.")
        return redirect("portal:lead_detail", pk=pk)


class LeadStageUpdateView(StaffRequiredMixin, View):
    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk)
        new_stage = request.POST.get("stage")
        valid = {value for value, _ in LeadStage.choices}
        if new_stage not in valid:
            messages.error(request, "Invalid stage.")
            return redirect("portal:lead_detail", pk=pk)
        lost_reason = request.POST.get("lost_reason", "") or ""
        lead.transition_to(
            new_stage, by_user=request.user, lost_reason=lost_reason
        )
        audit_log(
            "lead.stage_change",
            request=request,
            target=lead,
            to_stage=new_stage,
        )
        messages.success(request, f"Lead moved to {lead.get_stage_display()}.")
        return redirect("portal:lead_detail", pk=pk)


class LeadConvertView(StaffRequiredMixin, View):
    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk)
        if lead.converted_client_id is not None:
            messages.info(request, "This lead has already been converted.")
            return redirect("portal:client_detail", pk=lead.converted_client_id)
        client = lead.convert_to_client(by_user=request.user)
        audit_log(
            "lead.convert", request=request, target=lead, client_id=client.pk
        )
        messages.success(request, f"Converted to client #{client.pk}.")
        return redirect("portal:client_detail", pk=client.pk)
