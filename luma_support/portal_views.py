"""Server-rendered portal views (Django templates).

Kept thin — all business logic lives in the apps. These views
compose querysets and render templates so Marco can drive the
ticketing system from a browser without using the API directly.
"""
from django import forms
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
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

from clients.models import Client, Contact, System
from knowledge.models import Article
from tickets.models import CsatResponse, Ticket, TicketNote, TimeEntry


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict a portal view to staff (admin/engineer) and superusers."""

    raise_exception = False

    def test_func(self) -> bool:
        u = self.request.user
        return bool(u.is_authenticated and getattr(u, "can_view_all", False))

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        return redirect("portal:dashboard")


def _scope_tickets(qs, user):
    if user.can_view_all:
        return qs
    return qs.filter(client_id=user.client_id) if user.client_id else qs.none()


def _scope_clients(qs, user):
    if user.can_view_all:
        return qs
    return qs.filter(pk=user.client_id) if user.client_id else qs.none()


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
        from datetime import timedelta

        from django.db.models import Avg
        from django.template.response import TemplateResponse

        open_q = ~Q(status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED])
        tickets = _scope_tickets(Ticket.objects.all(), request.user)
        clients = _scope_clients(Client.objects.all(), request.user)
        by_priority = (
            tickets.filter(open_q)
            .values("priority")
            .annotate(count=Count("id"))
            .order_by("priority")
        )
        sla_warnings = _scope_tickets(Ticket.objects.sla_warnings(), request.user)[:10]
        recent = tickets.select_related("client", "assigned_to").order_by(
            "-created_at"
        )[:10]

        # 30-day CSAT roll-up. Scoped to the user's tickets so client
        # users only see their own response history.
        csat_since = timezone.now() - timedelta(days=30)
        csat_qs = CsatResponse.objects.filter(
            ticket__in=tickets, rating__isnull=False, responded_at__gte=csat_since
        )
        csat = csat_qs.aggregate(avg=Avg("rating"))["avg"]
        csat_count = csat_qs.count()

        context = {
            "by_priority": list(by_priority),
            "sla_warnings": sla_warnings,
            "recent": recent,
            "open_count": tickets.filter(open_q).count(),
            "client_count": clients.count(),
            "csat_avg": csat,
            "csat_count": csat_count,
            "active": "dashboard",
        }
        return TemplateResponse(request, self.template_name, context)


# ---------------------------------------------------------------------
# CSAT (public — tokenized, no auth required)
# ---------------------------------------------------------------------


class CsatSubmitView(View):
    """Public, single-use CSAT submission keyed by token from the email."""

    form_template = "portal/csat_form.html"
    thanks_template = "portal/csat_thanks.html"

    def get(self, request, token):
        csat = get_object_or_404(CsatResponse, token=token)
        if csat.rating is not None:
            return self._thanks(request, csat, already=True)
        return self._form(request, csat)

    def post(self, request, token):
        csat = get_object_or_404(CsatResponse, token=token)
        if csat.rating is not None:
            return self._thanks(request, csat, already=True)
        try:
            rating = int(request.POST.get("rating") or 0)
        except (TypeError, ValueError):
            rating = 0
        if not 1 <= rating <= 5:
            return self._form(request, csat, error="Please pick a rating from 1 to 5.")
        csat.rating = rating
        csat.comment = (request.POST.get("comment") or "").strip()
        csat.responded_at = timezone.now()
        csat.save(update_fields=["rating", "comment", "responded_at"])
        return self._thanks(request, csat, already=False)

    @staticmethod
    def _form(request, csat, error=None):
        from django.template.response import TemplateResponse

        return TemplateResponse(
            request,
            CsatSubmitView.form_template,
            {"csat": csat, "error": error},
        )

    @staticmethod
    def _thanks(request, csat, already=False):
        from django.template.response import TemplateResponse

        return TemplateResponse(
            request,
            CsatSubmitView.thanks_template,
            {"csat": csat, "already": already},
        )


# ---------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------


class TicketListView(LoginRequiredMixin, ListView):
    model = Ticket
    template_name = "portal/ticket_list.html"
    paginate_by = 50
    context_object_name = "tickets"

    def get_queryset(self):
        qs = _scope_tickets(
            Ticket.objects.select_related("client", "assigned_to", "system"),
            self.request.user,
        )
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
        ctx["clients"] = _scope_clients(
            Client.objects.all(), self.request.user
        ).order_by("name")
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

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        user = self.request.user
        if not user.can_view_all:
            if not user.client_id:
                raise PermissionDenied(
                    "Your account is not linked to a client."
                )
            form.fields["client"].queryset = Client.objects.filter(
                pk=user.client_id
            )
            form.fields["client"].initial = user.client_id
            form.fields["client"].disabled = True
            form.fields["system"].queryset = System.objects.filter(
                client_id=user.client_id
            )
            # Hide internal-only assignment for client users.
            form.fields.pop("assigned_to", None)
        return form

    def form_valid(self, form):
        user = self.request.user
        form.instance.created_by = user
        if not user.can_view_all:
            form.instance.client_id = user.client_id
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
        return _scope_tickets(
            Ticket.objects.select_related(
                "client", "system", "assigned_to", "created_by"
            ),
            self.request.user,
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "tickets"
        ctx["time_entries"] = self.object.time_entries.select_related("user")
        ctx["attachments"] = self.object.attachments.all()
        notes = self.object.notes.select_related("author").order_by("created_at")
        if not self.request.user.can_view_all:
            notes = notes.filter(internal=False)
        ctx["notes"] = notes
        ctx["status_choices"] = Ticket.Status.choices
        ctx["now"] = timezone.now()
        return ctx


class TicketStatusUpdateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        ticket = get_object_or_404(_scope_tickets(Ticket.objects.all(), request.user), pk=pk)
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


class TimeEntryCreateView(StaffRequiredMixin, View):
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
        ticket = get_object_or_404(
            _scope_tickets(Ticket.objects.all(), request.user), pk=pk
        )
        body = request.POST.get("body", "").strip()
        # Only staff can create internal notes; client users always file public notes.
        is_internal = (
            request.user.can_view_all and request.POST.get("internal") == "on"
        )
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
        qs = _scope_clients(Client.objects.all(), self.request.user)
        return qs.annotate(
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


def _sync_primary_contact(client: Client) -> None:
    """Mirror Client.name/email/phone onto a single primary Contact row."""
    primary = client.contacts.filter(is_primary=True).first()
    if primary is None:
        Contact.objects.create(
            client=client,
            name=client.name,
            email=client.email,
            phone=client.phone,
            is_primary=True,
        )
        return
    primary.name = client.name
    primary.email = client.email
    primary.phone = client.phone
    primary.save(update_fields=["name", "email", "phone", "updated_at"])


class ClientCreateView(StaffRequiredMixin, CreateView):
    model = Client
    form_class = ClientForm
    template_name = "portal/client_form.html"

    def get_success_url(self):
        return reverse("portal:client_detail", args=[self.object.pk])

    def form_valid(self, form):
        response = super().form_valid(form)
        _sync_primary_contact(self.object)
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "clients"
        return ctx


class ClientUpdateView(StaffRequiredMixin, UpdateView):
    model = Client
    form_class = ClientForm
    template_name = "portal/client_form.html"

    def get_success_url(self):
        return reverse("portal:client_detail", args=[self.object.pk])

    def form_valid(self, form):
        response = super().form_valid(form)
        _sync_primary_contact(self.object)
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "clients"
        return ctx


class ClientDetailView(LoginRequiredMixin, DetailView):
    model = Client
    template_name = "portal/client_detail.html"
    context_object_name = "client"

    def get_queryset(self):
        return _scope_clients(Client.objects.all(), self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["systems"] = self.object.systems.all()
        ctx["contacts"] = self.object.contacts.all()
        ctx["tickets"] = self.object.tickets.select_related("assigned_to").order_by(
            "-created_at"
        )[:50]
        ctx["active"] = "clients"
        return ctx


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ["name", "email", "phone", "title", "is_primary"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input"}),
            "email": forms.EmailInput(attrs={"class": "form-input"}),
            "phone": forms.TextInput(attrs={"class": "form-input"}),
            "title": forms.TextInput(attrs={"class": "form-input"}),
        }


class ContactCreateView(StaffRequiredMixin, View):
    template_name = "portal/contact_form.html"

    def get(self, request, client_pk):
        from django.template.response import TemplateResponse

        client = get_object_or_404(Client, pk=client_pk)
        return TemplateResponse(
            request,
            self.template_name,
            {"form": ContactForm(), "client": client, "active": "clients"},
        )

    def post(self, request, client_pk):
        from django.template.response import TemplateResponse

        client = get_object_or_404(Client, pk=client_pk)
        form = ContactForm(request.POST)
        if not form.is_valid():
            return TemplateResponse(
                request,
                self.template_name,
                {"form": form, "client": client, "active": "clients"},
            )
        contact = form.save(commit=False)
        contact.client = client
        if contact.is_primary:
            client.contacts.filter(is_primary=True).update(is_primary=False)
            client.name = contact.name
            client.email = contact.email
            client.phone = contact.phone
            client.save(update_fields=["name", "email", "phone", "updated_at"])
        contact.save()
        messages.success(request, f"Added contact {contact.name}.")
        return redirect("portal:client_detail", pk=client.pk)


class ContactUpdateView(StaffRequiredMixin, View):
    template_name = "portal/contact_form.html"

    def get(self, request, pk):
        from django.template.response import TemplateResponse

        contact = get_object_or_404(Contact, pk=pk)
        return TemplateResponse(
            request,
            self.template_name,
            {
                "form": ContactForm(instance=contact),
                "client": contact.client,
                "contact": contact,
                "active": "clients",
            },
        )

    def post(self, request, pk):
        from django.template.response import TemplateResponse

        contact = get_object_or_404(Contact, pk=pk)
        form = ContactForm(request.POST, instance=contact)
        if not form.is_valid():
            return TemplateResponse(
                request,
                self.template_name,
                {
                    "form": form,
                    "client": contact.client,
                    "contact": contact,
                    "active": "clients",
                },
            )
        updated = form.save(commit=False)
        if updated.is_primary:
            contact.client.contacts.filter(is_primary=True).exclude(
                pk=contact.pk
            ).update(is_primary=False)
            contact.client.name = updated.name
            contact.client.email = updated.email
            contact.client.phone = updated.phone
            contact.client.save(
                update_fields=["name", "email", "phone", "updated_at"]
            )
        updated.save()
        messages.success(request, f"Updated contact {updated.name}.")
        return redirect("portal:client_detail", pk=contact.client_id)


class ContactDeleteView(StaffRequiredMixin, View):
    def post(self, request, pk):
        contact = get_object_or_404(Contact, pk=pk)
        client_id = contact.client_id
        if contact.is_primary:
            messages.error(
                request,
                "Cannot delete the primary contact. Promote another contact first.",
            )
        else:
            contact.delete()
            messages.success(request, "Contact removed.")
        return redirect("portal:client_detail", pk=client_id)


# ---------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------


def _scope_articles(user):
    if user.can_view_all:
        return Article.objects.published()
    return Article.objects.visible_to_clients()


class ArticleListView(LoginRequiredMixin, ListView):
    model = Article
    template_name = "portal/kb_list.html"
    paginate_by = 30
    context_object_name = "articles"

    def get_queryset(self):
        qs = _scope_articles(self.request.user)
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

    def get_queryset(self):
        return _scope_articles(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "kb"
        return ctx
