"""Server-rendered portal views (Django templates).

Kept thin — all business logic lives in the apps. These views
compose querysets and render templates so Marco can drive the
ticketing system from a browser without using the API directly.
"""
from django import forms
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import (
    CreateView,
    DetailView,
    FormView,
    ListView,
    UpdateView,
)

from clients.models import Client, System
from knowledge.models import Article
from tickets.models import Ticket, TicketNote, TimeEntry


# ---------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={"class": "form-input", "placeholder": "you@example.com"}
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"class": "form-input", "placeholder": "Password"}
        )
    )


class LoginView(FormView):
    template_name = "portal/login.html"
    form_class = LoginForm
    success_url = reverse_lazy("portal:dashboard")

    def form_valid(self, form):
        user = authenticate(
            self.request,
            email=form.cleaned_data["email"],
            password=form.cleaned_data["password"],
        )
        if user is None:
            messages.error(self.request, "Invalid email or password.")
            return self.form_invalid(form)
        login(self.request, user)
        return super().form_valid(form)


# ---------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------


class DashboardView(LoginRequiredMixin, View):
    template_name = "portal/dashboard.html"

    def get(self, request):
        from django.template.response import TemplateResponse

        open_q = ~Q(status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED])
        by_priority = (
            Ticket.objects.filter(open_q)
            .values("priority")
            .annotate(count=Count("id"))
            .order_by("priority")
        )
        sla_warnings = Ticket.objects.sla_warnings()[:10]
        recent = Ticket.objects.select_related("client", "assigned_to").order_by(
            "-created_at"
        )[:10]
        context = {
            "by_priority": list(by_priority),
            "sla_warnings": sla_warnings,
            "recent": recent,
            "open_count": Ticket.objects.filter(open_q).count(),
            "client_count": Client.objects.count(),
            "active": "dashboard",
        }
        return TemplateResponse(request, self.template_name, context)


# ---------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------


class TicketListView(LoginRequiredMixin, ListView):
    model = Ticket
    template_name = "portal/ticket_list.html"
    paginate_by = 50
    context_object_name = "tickets"

    def get_queryset(self):
        qs = Ticket.objects.select_related("client", "assigned_to", "system")
        status = self.request.GET.get("status")
        priority = self.request.GET.get("priority")
        client = self.request.GET.get("client")
        if status:
            qs = qs.filter(status=status)
        if priority:
            qs = qs.filter(priority=priority)
        if client:
            qs = qs.filter(client_id=client)
        return qs.order_by("sla_deadline", "-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["clients"] = Client.objects.order_by("name")
        ctx["statuses"] = Ticket.Status.choices
        ctx["priorities"] = Ticket.Priority.choices
        ctx["filters"] = {
            "status": self.request.GET.get("status", ""),
            "priority": self.request.GET.get("priority", ""),
            "client": self.request.GET.get("client", ""),
        }
        ctx["active"] = "tickets"
        ctx["now"] = timezone.now()
        return ctx


class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["client", "system", "subject", "description", "priority", "assigned_to"]
        widgets = {
            "subject": forms.TextInput(attrs={"class": "form-input"}),
            "description": forms.Textarea(attrs={"class": "form-input", "rows": 6}),
            "priority": forms.Select(attrs={"class": "form-input"}),
            "client": forms.Select(attrs={"class": "form-input"}),
            "system": forms.Select(attrs={"class": "form-input"}),
            "assigned_to": forms.Select(attrs={"class": "form-input"}),
        }


class TicketCreateView(LoginRequiredMixin, CreateView):
    model = Ticket
    form_class = TicketForm
    template_name = "portal/ticket_form.html"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("portal:ticket_detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "tickets"
        return ctx


class TicketDetailView(LoginRequiredMixin, DetailView):
    model = Ticket
    template_name = "portal/ticket_detail.html"
    context_object_name = "ticket"

    def get_queryset(self):
        return Ticket.objects.select_related(
            "client", "system", "assigned_to", "created_by"
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "tickets"
        ctx["time_entries"] = self.object.time_entries.select_related("user")
        ctx["attachments"] = self.object.attachments.all()
        ctx["notes"] = self.object.notes.select_related("author").order_by("created_at")
        ctx["status_choices"] = Ticket.Status.choices
        ctx["now"] = timezone.now()
        return ctx


class TicketStatusUpdateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk)
        new_status = request.POST.get("status")
        valid = {value for value, _ in Ticket.Status.choices}
        if new_status not in valid:
            messages.error(request, "Invalid status.")
        else:
            ticket.transition_to(new_status, by_user=request.user)
            messages.success(request, f"Ticket marked {ticket.get_status_display()}.")
        return redirect("portal:ticket_detail", pk=pk)


class TimeEntryForm(forms.ModelForm):
    class Meta:
        model = TimeEntry
        fields = ["minutes", "description", "billable"]
        widgets = {
            "minutes": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "description": forms.TextInput(attrs={"class": "form-input"}),
        }


class TimeEntryCreateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk)
        form = TimeEntryForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.ticket = ticket
            entry.user = request.user
            entry.save()
            messages.success(request, f"Logged {entry.minutes} minutes.")
        else:
            messages.error(request, "Invalid time entry.")
        return redirect("portal:ticket_detail", pk=pk)


class TicketNoteCreateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk)
        body = request.POST.get("body", "").strip()
        is_internal = request.POST.get("internal") == "on"
        if not body:
            messages.error(request, "Note cannot be empty.")
        else:
            TicketNote.objects.create(
                ticket=ticket,
                author=request.user,
                body=body,
                internal=is_internal,
            )
            messages.success(request, "Note added.")
        return redirect("portal:ticket_detail", pk=pk)


# ---------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------


class ClientListView(LoginRequiredMixin, ListView):
    model = Client
    template_name = "portal/client_list.html"
    paginate_by = 50
    context_object_name = "clients"

    def get_queryset(self):
        return Client.objects.annotate(
            open_tickets=Count(
                "tickets",
                filter=~Q(
                    tickets__status__in=[
                        Ticket.Status.RESOLVED,
                        Ticket.Status.CLOSED,
                    ]
                ),
            )
        ).order_by("name")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "clients"
        return ctx


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            "name",
            "company",
            "customer_type",
            "email",
            "phone",
            "address",
            "billing_address",
            "vat_number",
            "care_plan_tier",
            "care_plan_start",
            "care_plan_renewal",
            "hourly_rate",
            "monthly_fee",
            "notes",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input"}),
            "company": forms.TextInput(attrs={"class": "form-input"}),
            "customer_type": forms.Select(attrs={"class": "form-input"}),
            "email": forms.EmailInput(attrs={"class": "form-input"}),
            "phone": forms.TextInput(attrs={"class": "form-input"}),
            "address": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
            "billing_address": forms.Textarea(
                attrs={"class": "form-input", "rows": 3}
            ),
            "vat_number": forms.TextInput(attrs={"class": "form-input"}),
            "care_plan_tier": forms.Select(attrs={"class": "form-input"}),
            "care_plan_start": forms.DateInput(
                attrs={"class": "form-input", "type": "date"}
            ),
            "care_plan_renewal": forms.DateInput(
                attrs={"class": "form-input", "type": "date"}
            ),
            "hourly_rate": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.01", "min": "0"}
            ),
            "monthly_fee": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.01", "min": "0"}
            ),
            "notes": forms.Textarea(attrs={"class": "form-input", "rows": 4}),
        }


class ClientCreateView(LoginRequiredMixin, CreateView):
    model = Client
    form_class = ClientForm
    template_name = "portal/client_form.html"
    success_url = reverse_lazy("portal:client_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "clients"
        return ctx


class ClientUpdateView(LoginRequiredMixin, UpdateView):
    model = Client
    form_class = ClientForm
    template_name = "portal/client_form.html"

    def get_success_url(self):
        return reverse("portal:client_detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "clients"
        return ctx


class ClientDetailView(LoginRequiredMixin, DetailView):
    model = Client
    template_name = "portal/client_detail.html"
    context_object_name = "client"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["systems"] = self.object.systems.all()
        ctx["tickets"] = self.object.tickets.select_related("assigned_to").order_by(
            "-created_at"
        )[:50]
        ctx["active"] = "clients"
        return ctx


# ---------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------


class ArticleListView(LoginRequiredMixin, ListView):
    model = Article
    template_name = "portal/kb_list.html"
    paginate_by = 30
    context_object_name = "articles"

    def get_queryset(self):
        qs = Article.objects.published()
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(content__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "kb"
        ctx["q"] = self.request.GET.get("q", "")
        return ctx


class ArticleDetailView(LoginRequiredMixin, DetailView):
    model = Article
    template_name = "portal/kb_detail.html"
    context_object_name = "article"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "kb"
        return ctx
