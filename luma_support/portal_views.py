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
from django.shortcuts import get_object_or_404, redirect, render
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
from luma_support.exports import CsvExportMixin
from notifications.models import Notification
from tickets.models import CsatResponse, MaintenanceSchedule, Ticket, TicketNote, TimeEntry


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

        # Staff (admin / engineer) must have 2FA — either verify it now
        # or enrol before we grant them a session. Client users are
        # exempt for v1 (most are casual portal visitors).
        if user.totp_enabled:
            self.request.session["pending_totp_user_id"] = user.pk
            return redirect("portal:totp_verify")
        if user.is_engineer:  # covers admin + engineer
            self.request.session["pending_totp_user_id"] = user.pk
            return redirect("portal:totp_setup")

        login(self.request, user)
        return super().form_valid(form)


class _PendingUserMixin:
    """Resolve the user mid-login (after password, before TOTP)."""

    def _pending_user(self, request):
        user_id = request.session.get("pending_totp_user_id")
        if not user_id:
            return None
        from django.contrib.auth import get_user_model

        User = get_user_model()
        return User.objects.filter(pk=user_id).first()


class TotpSetupView(_PendingUserMixin, View):
    template_name = "portal/totp_setup.html"

    def get(self, request):
        import pyotp
        from django.template.response import TemplateResponse

        user = self._pending_user(request)
        if user is None:
            return redirect("portal:login")
        secret = request.session.get("pending_totp_secret") or pyotp.random_base32()
        request.session["pending_totp_secret"] = secret
        uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=user.email, issuer_name="Luma Tech Solutions"
        )
        return TemplateResponse(
            request,
            self.template_name,
            {
                "secret": secret,
                "provisioning_uri": uri,
                "qr_svg_url": reverse("portal:totp_qr"),
                "user_email": user.email,
            },
        )

    def post(self, request):
        import pyotp

        from accounts.models import RecoveryCode

        user = self._pending_user(request)
        secret = request.session.get("pending_totp_secret")
        if user is None or not secret:
            return redirect("portal:login")
        code = (request.POST.get("code") or "").strip().replace(" ", "")
        if not pyotp.TOTP(secret).verify(code, valid_window=1):
            messages.error(request, "Code didn't match. Try again.")
            return self.get(request)
        user.set_totp_secret(secret)
        user.totp_enabled = True
        user.save(update_fields=["totp_secret_encrypted", "totp_enabled"])
        request.session.pop("pending_totp_user_id", None)
        request.session.pop("pending_totp_secret", None)
        login(request, user)
        # First-time enrolment: generate recovery codes and stash them in
        # the session so the next page can show them once.
        codes = RecoveryCode.regenerate_for(user)
        request.session["fresh_recovery_codes"] = codes
        return redirect("portal:recovery_codes")


class RecoveryCodesView(LoginRequiredMixin, View):
    template_name = "portal/recovery_codes.html"

    def get(self, request):
        from django.template.response import TemplateResponse

        codes = request.session.pop("fresh_recovery_codes", None)
        remaining = request.user.recovery_codes.filter(used_at__isnull=True).count()
        return TemplateResponse(
            request,
            self.template_name,
            {"codes": codes, "remaining": remaining, "active": "profile"},
        )

    def post(self, request):
        from accounts.models import RecoveryCode

        codes = RecoveryCode.regenerate_for(request.user)
        request.session["fresh_recovery_codes"] = codes
        messages.success(
            request, "Recovery codes regenerated — old codes are now invalid."
        )
        return redirect("portal:recovery_codes")


class TotpVerifyView(_PendingUserMixin, View):
    template_name = "portal/totp_verify.html"

    def get(self, request):
        from django.template.response import TemplateResponse

        if self._pending_user(request) is None:
            return redirect("portal:login")
        return TemplateResponse(request, self.template_name, {})

    def post(self, request):
        import pyotp

        user = self._pending_user(request)
        if user is None:
            return redirect("portal:login")
        secret = user.get_totp_secret()
        code = (request.POST.get("code") or "").strip().replace(" ", "")
        if not secret or not pyotp.TOTP(secret).verify(code, valid_window=1):
            messages.error(request, "Invalid code.")
            return self.get(request)
        request.session.pop("pending_totp_user_id", None)
        login(request, user)
        return redirect("portal:dashboard")


class TotpQrView(_PendingUserMixin, View):
    """Inline SVG QR for the pending enrolment secret. Same-origin only."""

    def get(self, request):
        import pyotp
        import qrcode
        import qrcode.image.svg as qrsvg
        from django.http import HttpResponse, HttpResponseNotFound

        user = self._pending_user(request)
        secret = request.session.get("pending_totp_secret")
        if user is None or not secret:
            return HttpResponseNotFound()
        uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=user.email, issuer_name="Luma Tech Solutions"
        )
        img = qrcode.make(uri, image_factory=qrsvg.SvgPathImage, box_size=10)
        from io import BytesIO

        buf = BytesIO()
        img.save(buf)
        return HttpResponse(buf.getvalue(), content_type="image/svg+xml")


# ---------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------


class DashboardView(LoginRequiredMixin, View):
    template_name = "portal/dashboard.html"

    def get(self, request):
        from datetime import timedelta
        from decimal import Decimal

        from django.conf import settings as dj_settings
        from django.db.models import Avg, Sum
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

        # Staff-only operational metrics: revenue, unbilled hours,
        # overdue invoices, upcoming maintenance.
        if request.user.can_view_all:
            from billing.models import Invoice, Payment
            from social.models import InboxStatus, SocialAccount, SocialInboxItem
            from tickets.models import MaintenanceSchedule, TimeEntry

            now = timezone.now()
            month_start = now.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )

            unbilled_minutes = (
                TimeEntry.objects.filter(billable=True, invoice_line__isnull=True)
                .aggregate(total=Sum("minutes"))["total"]
                or 0
            )
            mtd_invoiced = (
                Invoice.objects.filter(created_at__gte=month_start)
                .aggregate(total=Sum("total"))["total"]
                or Decimal("0")
            )
            mtd_paid = (
                Payment.objects.filter(paid_at__gte=month_start)
                .aggregate(total=Sum("amount"))["total"]
                or Decimal("0")
            )
            overdue_count = Invoice.objects.filter(
                status__in=[Invoice.Status.SENT, Invoice.Status.AUTHORISED],
                due_date__lt=timezone.localdate(),
            ).count()
            schedules_due = MaintenanceSchedule.objects.filter(
                active=True,
                next_run_at__lte=timezone.localdate() + timedelta(days=7),
            ).count()

            from clients.health import clients_at_risk

            at_risk = clients_at_risk(limit=5)
            risk_clients = {
                c.pk: c
                for c in Client.objects.filter(
                    pk__in=[s.client_id for s in at_risk]
                )
            }
            at_risk_rows = [
                {"score": s, "client": risk_clients[s.client_id]}
                for s in at_risk
                if s.client_id in risk_clients
            ]
            from clients.fernet_status import snapshot as _fernet_snapshot
            from system.integrations_health import snapshot as _int_snapshot

            integrations = _int_snapshot()
            fernet = _fernet_snapshot()
            context.update(
                {
                    "unbilled_hours": (Decimal(unbilled_minutes) / Decimal(60)).quantize(
                        Decimal("0.1")
                    ),
                    "mtd_invoiced": mtd_invoiced,
                    "mtd_paid": mtd_paid,
                    "overdue_count": overdue_count,
                    "schedules_due": schedules_due,
                    "at_risk_clients": at_risk_rows,
                    "default_currency": getattr(dj_settings, "DEFAULT_CURRENCY", "GBP"),
                    "integrations_health": integrations,
                    "integrations_failing": [
                        r for r in integrations if r["configured"] and not r["ok"]
                    ],
                    "fernet_status": fernet,
                }
            )

            # Social section is hidden until Marco connects his first
            # account — keeps the dashboard unchanged for users with no
            # platforms wired up yet.
            social_accounts = list(SocialAccount.objects.all())
            if social_accounts:
                social_inbox = (
                    SocialInboxItem.objects.filter(status=InboxStatus.OPEN)
                    .select_related("account")
                    .order_by("received_at")[:10]
                )
                context.update(
                    {
                        "social_accounts": social_accounts,
                        "social_inbox": social_inbox,
                        "social_health_warnings": [
                            a for a in social_accounts if a.health_status not in ("", "ok")
                        ],
                    }
                )
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


class TicketListView(CsvExportMixin, LoginRequiredMixin, ListView):
    model = Ticket
    template_name = "portal/ticket_list.html"
    paginate_by = 50
    context_object_name = "tickets"
    csv_filename = "tickets"
    csv_columns = (
        ("id", "pk"),
        ("subject", "subject"),
        ("client", "client.name"),
        ("system", "system.name"),
        ("priority", "get_priority_display"),
        ("status", "get_status_display"),
        ("assigned_to", "assigned_to.email"),
        ("sla_deadline", "sla_deadline"),
        ("effective_sla_deadline", "effective_sla_deadline"),
        ("is_paused", "is_paused"),
        ("is_breached", "is_breached"),
        ("created_at", "created_at"),
        ("resolved_at", "resolved_at"),
        ("closed_at", "closed_at"),
    )

    def get_queryset(self):
        qs = _scope_tickets(
            Ticket.objects.select_related(
                "client", "assigned_to", "system"
            ).prefetch_related("tags"),
            self.request.user,
        )
        status = self.request.GET.get("status")
        priority = self.request.GET.get("priority")
        client = self.request.GET.get("client")
        tag_slug = self.request.GET.get("tag")
        if status:
            qs = qs.filter(status=status)
        if priority:
            qs = qs.filter(priority=priority)
        if client:
            qs = qs.filter(client_id=client)
        if tag_slug:
            qs = qs.filter(tags__slug=tag_slug)
        return qs.order_by("sla_deadline", "-created_at")

    def get_context_data(self, **kwargs):
        from tickets.models import SavedTicketFilter, TicketTag

        ctx = super().get_context_data(**kwargs)
        ctx["clients"] = _scope_clients(
            Client.objects.all(), self.request.user
        ).order_by("name")
        ctx["statuses"] = Ticket.Status.choices
        ctx["priorities"] = Ticket.Priority.choices
        ctx["tags"] = TicketTag.objects.all()
        ctx["filters"] = {
            "status": self.request.GET.get("status", ""),
            "priority": self.request.GET.get("priority", ""),
            "client": self.request.GET.get("client", ""),
            "tag": self.request.GET.get("tag", ""),
        }
        ctx["saved_filters"] = list(
            SavedTicketFilter.objects.filter(user=self.request.user, pinned=True)
        )
        ctx["current_qs"] = self.request.GET.urlencode()
        ctx["active"] = "tickets"
        ctx["now"] = timezone.now()
        return ctx


class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = [
            "client",
            "system",
            "subject",
            "description",
            "priority",
            "assigned_to",
            "tags",
        ]
        widgets = {
            "subject": forms.TextInput(attrs={"class": "form-input"}),
            "description": forms.Textarea(attrs={"class": "form-input", "rows": 6}),
            "priority": forms.Select(attrs={"class": "form-input"}),
            "client": forms.Select(attrs={"class": "form-input"}),
            "system": forms.Select(attrs={"class": "form-input"}),
            "assigned_to": forms.Select(attrs={"class": "form-input"}),
            "tags": forms.CheckboxSelectMultiple(),
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
            form.fields.pop("tags", None)
        return form

    def form_valid(self, form):
        user = self.request.user
        form.instance.created_by = user
        if not user.can_view_all:
            form.instance.client_id = user.client_id
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("portal:ticket_detail", args=[self.object.pk])

    def post(self, request, *args, **kwargs):
        # "Suggest articles" doesn't save — it asks the KB AI helper for
        # similar published articles and re-renders the form.
        if request.POST.get("_action") == "suggest":
            from knowledge.ai import suggest_articles

            subject = request.POST.get("subject", "")
            description = request.POST.get("description", "")
            self.object = None
            form = self.get_form()
            form.is_valid()  # populate errors but don't save
            suggestions = suggest_articles(
                subject,
                description,
                client_visible_only=not request.user.can_view_all,
            )
            return self.render_to_response(
                self.get_context_data(form=form, kb_suggestions=suggestions)
            )
        return super().post(request, *args, **kwargs)

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

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        # Stamp the read-receipt only when the viewer is a client user.
        # Staff opens don't move the marker.
        if (
            getattr(self.object, "pk", None)
            and getattr(request.user, "is_client", False)
        ):
            Ticket.objects.filter(pk=self.object.pk).update(
                client_last_viewed_at=timezone.now()
            )
        return response

    def get_context_data(self, **kwargs):
        from tickets.models import TicketTemplate

        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "tickets"
        ctx["time_entries"] = self.object.time_entries.select_related("user")
        ctx["attachments"] = self.object.attachments.all()
        notes = self.object.notes.select_related("author").order_by("created_at")
        if not self.request.user.can_view_all:
            notes = notes.filter(internal=False)
        ctx["notes"] = notes
        ctx["status_choices"] = Ticket.Status.choices
        if self.request.user.can_view_all:
            ctx["note_templates"] = TicketTemplate.objects.all()
        else:
            ctx["note_templates"] = []
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


class ClientMonthlyReportView(StaffRequiredMixin, View):
    """Stream a PDF monthly support summary for ``client``.

    Wraps ``tickets.reports.build_monthly_report_pdf`` — the same call
    the Celery monthly-send task uses, so the email and the
    download-now button always render the same content.
    """

    def get(self, request, pk):
        from django.http import HttpResponse

        from tickets.reports import build_monthly_report_pdf

        client = get_object_or_404(Client, pk=pk)
        today = timezone.localdate()
        try:
            year = int(request.GET.get("year", today.year))
            month = int(request.GET.get("month", today.month))
        except (TypeError, ValueError):
            messages.error(request, "Invalid year/month.")
            return redirect("portal:client_detail", pk=pk)
        if not (1 <= month <= 12) or year < 2000 or year > 2100:
            messages.error(request, "Year/month out of range.")
            return redirect("portal:client_detail", pk=pk)

        pdf_bytes = build_monthly_report_pdf(client, year, month)
        filename = f"luma-report-{client.pk}-{year}-{month:02d}.pdf"
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class TicketMergeView(LoginRequiredMixin, View):
    """Server-rendered counterpart to /api/v1/tickets/<id>/merge-into/.

    Posts ``target`` (integer ticket id) — moves notes / time / tags /
    attachments to the target and closes this one with a link back.
    """

    def post(self, request, pk):
        from django.http import HttpResponseForbidden

        from audit import log as audit_log

        if not request.user.can_view_all:
            return HttpResponseForbidden("Staff only.")
        source = get_object_or_404(Ticket, pk=pk)
        try:
            target_pk = int(request.POST.get("target") or 0)
            target = Ticket.objects.get(pk=target_pk)
        except (ValueError, Ticket.DoesNotExist):
            messages.error(request, "Pick an existing ticket to merge into.")
            return redirect("portal:ticket_detail", pk=pk)
        if source.pk == target.pk:
            messages.error(request, "Cannot merge a ticket into itself.")
            return redirect("portal:ticket_detail", pk=pk)
        if source.client_id != target.client_id:
            messages.error(
                request, "Merge target must belong to the same client."
            )
            return redirect("portal:ticket_detail", pk=pk)

        source.notes.update(ticket=target)
        source.time_entries.update(ticket=target)
        source.attachments.update(ticket=target)
        for tag in source.tags.all():
            target.tags.add(tag)
        TicketNote.objects.create(
            ticket=target,
            author=request.user,
            body=f"Merged #{source.pk} ({source.subject}) into this ticket.",
            internal=True,
        )
        TicketNote.objects.create(
            ticket=source,
            author=request.user,
            body=f"Merged into #{target.pk}. Closing.",
            internal=True,
        )
        source.transition_to(Ticket.Status.CLOSED, by_user=request.user)
        audit_log(
            "ticket.merge",
            actor=request.user,
            request=request,
            target=source,
            merged_into=target.pk,
        )
        messages.success(
            request, f"Merged ticket #{source.pk} into #{target.pk}."
        )
        return redirect("portal:ticket_detail", pk=target.pk)


class SavedTicketFilterCreateView(LoginRequiredMixin, View):
    """Server-rendered counterpart to the API. POST {name, querystring,
    pinned}."""

    def post(self, request):
        from tickets.models import SavedTicketFilter

        name = (request.POST.get("name") or "").strip()
        qs = (request.POST.get("querystring") or "").strip()
        pinned = request.POST.get("pinned") == "1"
        if not name or not qs:
            messages.error(request, "Name + querystring required.")
            return redirect("portal:ticket_list")
        SavedTicketFilter.objects.update_or_create(
            user=request.user, name=name,
            defaults={"querystring": qs, "pinned": pinned},
        )
        messages.success(request, f"Saved view “{name}”.")
        return redirect(f"/tickets/?{qs}")


class SavedTicketFilterDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        from tickets.models import SavedTicketFilter

        SavedTicketFilter.objects.filter(user=request.user, pk=pk).delete()
        return redirect("portal:ticket_list")


class TicketBulkActionView(LoginRequiredMixin, View):
    """Apply one action to multiple checked tickets from the list view.

    Server-rendered counterpart to the /api/v1/tickets/bulk/ endpoint;
    same semantics (and audit rows) but accepts an HTML form POST.
    """

    def post(self, request):
        from django.http import HttpResponseForbidden

        from audit import log as audit_log
        from tickets.models import TicketTag

        if not request.user.can_view_all:
            return HttpResponseForbidden("Staff only.")

        ids = [int(x) for x in request.POST.getlist("ids") if x.isdigit()]
        action_name = request.POST.get("action", "")
        value = request.POST.get("value") or None
        if not ids or not action_name:
            messages.error(request, "Pick at least one ticket and an action.")
            return redirect(request.META.get("HTTP_REFERER", "portal:ticket_list"))

        valid_statuses = {v for v, _ in Ticket.Status.choices}
        valid_priorities = {v for v, _ in Ticket.Priority.choices}
        touched = 0
        try:
            for ticket in Ticket.objects.filter(pk__in=ids):
                if action_name == "status":
                    if value not in valid_statuses:
                        raise ValueError("invalid status")
                    ticket.transition_to(value, by_user=request.user)
                elif action_name == "priority":
                    if value not in valid_priorities:
                        raise ValueError("invalid priority")
                    ticket.priority = value
                    ticket.save(update_fields=["priority"])
                elif action_name in ("add_tag", "remove_tag"):
                    if not value:
                        raise ValueError("tag required")
                    tag = (
                        TicketTag.objects.filter(pk=int(value)).first()
                        if value.isdigit()
                        else TicketTag.objects.filter(slug=value).first()
                    )
                    if tag is None:
                        raise ValueError("unknown tag")
                    if action_name == "add_tag":
                        ticket.tags.add(tag)
                    else:
                        ticket.tags.remove(tag)
                else:
                    raise ValueError(f"unknown action {action_name!r}")
                audit_log(
                    f"ticket.bulk.{action_name}",
                    actor=request.user,
                    request=request,
                    target=ticket,
                    value=value,
                )
                touched += 1
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect(request.META.get("HTTP_REFERER", "portal:ticket_list"))

        messages.success(request, f"Applied to {touched} ticket(s).")
        return redirect(request.META.get("HTTP_REFERER", "portal:ticket_list"))


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


class SiteVisitListView(StaffRequiredMixin, View):
    """Staff-only site-visit logbook for the web portal.

    Web parity for mobile/lib/src/screens/site_visits_screen.dart: list
    recent visits, start a visit for a client, and end an open visit
    (optionally billing its minutes to a ticket). Reuses the existing
    SiteVisit model + audit log; no new backend.
    """

    template_name = "portal/site_visit_list.html"

    def get(self, request):
        from clients.models import SiteVisit

        visits = list(
            SiteVisit.objects.select_related("client", "user")[:100]
        )
        return render(
            request,
            self.template_name,
            {
                "visits": visits,
                "open_visits": [v for v in visits if v.is_open],
                "clients": Client.objects.order_by("name"),
                "active": "site_visits",
            },
        )

    def post(self, request):
        from audit import log as audit_log
        from clients.models import SiteVisit
        from tickets.models import Ticket, TimeEntry

        action = request.POST.get("action")
        if action == "start":
            client = get_object_or_404(Client, pk=request.POST.get("client"))
            visit = SiteVisit.objects.create(client=client, user=request.user)
            audit_log(
                "site_visit.start",
                actor=request.user,
                request=request,
                target=client,
                visit_id=visit.pk,
            )
            messages.success(request, f"Started a visit at {client.name}.")
            return redirect("portal:site_visit_list")

        if action == "end":
            visit = get_object_or_404(SiteVisit, pk=request.POST.get("visit"))
            if visit.ended_at is not None:
                messages.error(request, "That visit is already closed.")
                return redirect("portal:site_visit_list")
            # Engineers can only close their own visits; admins can close any.
            if visit.user_id != request.user.pk and not request.user.is_admin_role:
                messages.error(request, "You can only end your own visits.")
                return redirect("portal:site_visit_list")

            visit.ended_at = timezone.now()
            notes = (request.POST.get("notes") or "").strip()
            if notes:
                visit.notes = visit.notes + ("\n" if visit.notes else "") + notes
            # Optionally bill the visit's minutes against a ticket for the client.
            ticket_id = request.POST.get("ticket") or ""
            if ticket_id.isdigit() and visit.duration_minutes:
                ticket = Ticket.objects.filter(
                    pk=int(ticket_id), client=visit.client
                ).first()
                if ticket is None:
                    messages.warning(
                        request,
                        "Ticket not found for that client — visit closed "
                        "without billing.",
                    )
                else:
                    visit.time_entry = TimeEntry.objects.create(
                        ticket=ticket,
                        user=visit.user,
                        minutes=visit.duration_minutes,
                        description=f"Site visit at {visit.client.name}",
                        billable=True,
                    )
            visit.save()
            audit_log(
                "site_visit.end",
                actor=request.user,
                request=request,
                target=visit.client,
                visit_id=visit.pk,
                minutes=visit.duration_minutes,
            )
            messages.success(request, "Visit ended.")
            return redirect("portal:site_visit_list")

        messages.error(request, "Unknown action.")
        return redirect("portal:site_visit_list")


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


class TicketDraftReplyView(LoginRequiredMixin, UserPassesTestMixin, View):
    """JSON: POST → {"draft": "..."}. Staff-only — clients don't draft replies."""

    raise_exception = True

    def test_func(self) -> bool:
        u = self.request.user
        return bool(u.is_authenticated and getattr(u, "can_view_all", False))

    def post(self, request, pk):
        from django.http import JsonResponse

        from tickets.ai import draft_reply

        ticket = get_object_or_404(Ticket, pk=pk)
        draft = draft_reply(ticket)
        return JsonResponse({"draft": draft})


# ---------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------


class ClientListView(CsvExportMixin, LoginRequiredMixin, ListView):
    model = Client
    template_name = "portal/client_list.html"
    paginate_by = 50
    context_object_name = "clients"
    csv_filename = "clients"
    csv_columns = (
        ("id", "pk"),
        ("name", "name"),
        ("company", "company"),
        ("email", "email"),
        ("phone", "phone"),
        ("vat_number", "vat_number"),
        ("care_plan_tier", "care_plan_tier"),
        ("monthly_fee", "monthly_fee"),
        ("hourly_rate", "hourly_rate"),
        ("created_at", "created_at"),
    )

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
        # Staff users see a health pill alongside each client — attach the
        # score to each row so the template can reference c.health.score.
        if self.request.user.can_view_all:
            from clients.health import score_clients

            page = ctx.get("clients") or []
            by_id = {h.client_id: h for h in score_clients(page)}
            for c in page:
                c.health = by_id.get(c.pk)
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
        if self.request.user.can_view_all:
            from clients.health import score_client

            ctx["health"] = score_client(self.object)
            tasks = list(
                self.object.onboarding_tasks.order_by("done", "order", "pk")
            )
            ctx["onboarding_tasks"] = tasks
            done = sum(1 for t in tasks if t.done)
            ctx["onboarding_done_count"] = done
            ctx["onboarding_percent"] = (
                int(round(100 * done / len(tasks))) if tasks else 0
            )
        return ctx


class ClientTimelineView(StaffRequiredMixin, View):
    """Unified per-client communication log — tickets, notes, quotes, invoices."""

    template_name = "portal/client_timeline.html"

    def get(self, request, pk):
        from django.template.response import TemplateResponse

        from clients.timeline import for_client

        client = get_object_or_404(Client, pk=pk)
        events = for_client(client)
        return TemplateResponse(
            request,
            self.template_name,
            {"client": client, "events": events, "active": "clients"},
        )


class OnboardingToggleView(StaffRequiredMixin, View):
    """Tick / untick a single onboarding task."""

    def post(self, request, pk):
        from django.utils import timezone as _tz

        from clients.models import ClientOnboardingTask

        task = get_object_or_404(ClientOnboardingTask, pk=pk)
        task.done = not task.done
        if task.done:
            task.completed_at = _tz.now()
            task.completed_by = request.user
        else:
            task.completed_at = None
            task.completed_by = None
        task.save(
            update_fields=["done", "completed_at", "completed_by"]
        )
        return redirect("portal:client_detail", pk=task.client_id)


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
    client = getattr(user, "client", None)
    if client is None:
        return Article.objects.none()
    return Article.objects.for_client(client)


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
        q = self.request.GET.get("q", "")
        ctx["q"] = q
        if q:
            from knowledge.views import _log_search

            _log_search(
                q,
                user=self.request.user,
                results_count=self.get_queryset().count(),
                source="portal",
            )
        return ctx


class TicketBoardView(LoginRequiredMixin, View):
    """Kanban-style ticket board grouped by status.

    No drag-and-drop in v1 — each card shows a tiny status form that
    POSTs to the existing TicketStatusUpdateView, so the round trip
    matches every other status transition on the system (audit log,
    SLA recompute, push fan-out all still fire).
    """

    template_name = "portal/ticket_board.html"

    def get(self, request):
        from django.template.response import TemplateResponse

        from tickets.models import TicketTag

        qs = _scope_tickets(
            Ticket.objects.select_related("client", "assigned_to")
                          .prefetch_related("tags"),
            request.user,
        ).exclude(status=Ticket.Status.CLOSED)

        tag_slug = request.GET.get("tag")
        if tag_slug:
            qs = qs.filter(tags__slug=tag_slug)

        lanes_order = [
            Ticket.Status.NEW,
            Ticket.Status.ASSIGNED,
            Ticket.Status.IN_PROGRESS,
            Ticket.Status.WAITING,
            Ticket.Status.RESOLVED,
        ]
        by_status = {s: [] for s in lanes_order}
        for ticket in qs.order_by("sla_deadline", "-created_at"):
            if ticket.status in by_status:
                by_status[ticket.status].append(ticket)

        lanes = [
            {
                "value": s,
                "label": dict(Ticket.Status.choices)[s],
                "tickets": by_status[s],
            }
            for s in lanes_order
        ]
        return TemplateResponse(
            request,
            self.template_name,
            {
                "active": "tickets",
                "lanes": lanes,
                "status_choices": Ticket.Status.choices,
                "tags": TicketTag.objects.all(),
                "tag_slug": tag_slug or "",
            },
        )


class SlaAnalyticsView(StaffRequiredMixin, View):
    """Staff-only SLA hit-rate report — per priority + worst clients."""

    template_name = "portal/sla_analytics.html"

    def get(self, request):
        from datetime import timedelta

        from django.db.models import Count, F, Q
        from django.template.response import TemplateResponse

        try:
            days = int(request.GET.get("days", 30))
        except (TypeError, ValueError):
            days = 30
        days = max(1, min(days, 365))
        since = timezone.now() - timedelta(days=days)

        closed_qs = Ticket.objects.filter(
            status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED],
            resolved_at__gte=since,
            sla_deadline__isnull=False,
        )

        def _rate(closed, met):
            return (met / closed) if closed else None

        totals = closed_qs.aggregate(
            closed=Count("id"),
            met=Count("id", filter=Q(resolved_at__lte=F("sla_deadline"))),
        )
        totals["breached"] = totals["closed"] - totals["met"]
        totals["hit_rate"] = _rate(totals["closed"], totals["met"])

        per_priority = []
        for prio, label in Ticket.Priority.choices:
            row = closed_qs.filter(priority=prio).aggregate(
                closed=Count("id"),
                met=Count("id", filter=Q(resolved_at__lte=F("sla_deadline"))),
            )
            if row["closed"]:
                row["priority"] = prio
                row["label"] = label
                row["breached"] = row["closed"] - row["met"]
                row["hit_rate"] = _rate(row["closed"], row["met"])
                per_priority.append(row)

        worst = (
            closed_qs.values("client_id", "client__name")
            .annotate(
                closed=Count("id"),
                breached=Count("id", filter=Q(resolved_at__gt=F("sla_deadline"))),
            )
            .filter(breached__gt=0)
            .order_by("-breached")[:10]
        )

        return TemplateResponse(
            request,
            self.template_name,
            {
                "active": "tickets",
                "window_days": days,
                "totals": totals,
                "per_priority": per_priority,
                "worst": list(worst),
            },
        )


class PublicStatusPageView(View):
    """Public per-client status page — no auth.

    Opted-in clients have a non-null ``status_page_slug``. The page
    lists each monitored system with its current health status and any
    recent high-priority tickets. Nothing in the response references
    other clients' data; the slug acts as a soft access control.
    """

    template_name = "portal/status_page.html"

    def get(self, request, slug):
        from datetime import timedelta

        from django.http import HttpResponseNotFound
        from django.template.response import TemplateResponse

        from tickets.models import Ticket

        client = Client.objects.filter(status_page_slug=slug).first()
        if client is None:
            return HttpResponseNotFound("status page not found")
        systems = client.systems.all().order_by("name")
        recent_window = timezone.now() - timedelta(days=30)
        recent_tickets = (
            Ticket.objects.filter(
                client=client,
                priority__in=[
                    Ticket.Priority.CRITICAL,
                    Ticket.Priority.HIGH,
                ],
                created_at__gte=recent_window,
            )
            .select_related("system")
            .order_by("-created_at")[:10]
        )
        return TemplateResponse(
            request,
            self.template_name,
            {
                "client": client,
                "systems": systems,
                "recent_tickets": recent_tickets,
                "active": "status",
            },
        )


class KbGapsReportView(StaffRequiredMixin, View):
    """Staff-only "topics with no articles" report.

    Aggregates KbSearchLog rows from the last N days where
    results_count == 0 and groups by normalised query, so Marco can see
    what to write next.
    """

    template_name = "portal/kb_gaps.html"

    def get(self, request):
        from datetime import timedelta

        from django.db.models import Count, Max
        from django.template.response import TemplateResponse

        from knowledge.models import KbSearchLog

        try:
            window_days = int(request.GET.get("days", 30))
        except (TypeError, ValueError):
            window_days = 30
        window_days = max(1, min(window_days, 365))
        since = timezone.now() - timedelta(days=window_days)

        rows = (
            KbSearchLog.objects.filter(created_at__gte=since)
            .values("query")
            .annotate(
                hits=Count("id"),
                zero=Count("id", filter=Q(results_count=0)),
                last_seen=Max("created_at"),
            )
            .order_by("-zero", "-hits")
        )
        gaps = [r for r in rows if r["zero"] > 0]
        return TemplateResponse(
            request,
            self.template_name,
            {
                "active": "kb",
                "gaps": gaps[:200],
                "popular": list(rows[:50]),
                "window_days": window_days,
            },
        )


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
        ctx["revisions_count"] = self.object.revisions.count()
        return ctx


class ArticleHistoryView(StaffRequiredMixin, View):
    template_name = "portal/kb_history.html"

    def get(self, request, slug):
        from django.template.response import TemplateResponse

        article = get_object_or_404(Article, slug=slug)
        revisions = article.revisions.select_related("edited_by")
        return TemplateResponse(
            request,
            self.template_name,
            {"article": article, "revisions": revisions, "active": "kb"},
        )


# ---------------------------------------------------------------------
# Maintenance schedules (staff only)
# ---------------------------------------------------------------------


class MaintenanceScheduleForm(forms.ModelForm):
    class Meta:
        model = MaintenanceSchedule
        fields = [
            "client",
            "system",
            "cadence",
            "next_run_at",
            "template_subject",
            "template_description",
            "priority",
            "default_assignee",
            "active",
        ]
        widgets = {
            "next_run_at": forms.DateInput(
                attrs={"class": "form-input", "type": "date"}
            ),
            "template_subject": forms.TextInput(attrs={"class": "form-input"}),
            "template_description": forms.Textarea(
                attrs={"class": "form-input", "rows": 4}
            ),
        }


class MaintenanceScheduleListView(StaffRequiredMixin, ListView):
    model = MaintenanceSchedule
    template_name = "portal/schedule_list.html"
    paginate_by = 50
    context_object_name = "schedules"

    def get_queryset(self):
        return MaintenanceSchedule.objects.select_related(
            "client", "system", "default_assignee"
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "schedules"
        return ctx


class MaintenanceScheduleCreateView(StaffRequiredMixin, CreateView):
    model = MaintenanceSchedule
    form_class = MaintenanceScheduleForm
    template_name = "portal/schedule_form.html"
    success_url = reverse_lazy("portal:schedule_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "schedules"
        return ctx


class MaintenanceScheduleUpdateView(StaffRequiredMixin, UpdateView):
    model = MaintenanceSchedule
    form_class = MaintenanceScheduleForm
    template_name = "portal/schedule_form.html"
    success_url = reverse_lazy("portal:schedule_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "schedules"
        return ctx


class MaintenanceScheduleDeleteView(StaffRequiredMixin, View):
    def post(self, request, pk):
        sched = get_object_or_404(MaintenanceSchedule, pk=pk)
        sched.delete()
        messages.success(request, "Maintenance schedule removed.")
        return redirect("portal:schedule_list")


# ---------------------------------------------------------------------
# My services (client-facing — current user's systems with health)
# ---------------------------------------------------------------------


class MyServicesView(LoginRequiredMixin, View):
    template_name = "portal/my_services.html"

    def get(self, request):
        from django.template.response import TemplateResponse

        if request.user.client_id is None:
            messages.info(request, "Your account isn't linked to a client.")
            return redirect("portal:dashboard")

        systems = (
            System.objects.filter(client_id=request.user.client_id)
            .order_by("name")
        )

        # Recent open tickets touching each system, so clients can see
        # what's already being worked on.
        recent_tickets = (
            Ticket.objects.filter(
                client_id=request.user.client_id,
                system__isnull=False,
            )
            .exclude(status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED])
            .select_related("system")
            .order_by("-created_at")[:10]
        )
        return TemplateResponse(
            request,
            self.template_name,
            {
                "systems": systems,
                "recent_tickets": recent_tickets,
                "active": "my_services",
            },
        )


# ---------------------------------------------------------------------
# Notifications (in-app feed — parity with the mobile inbox)
# ---------------------------------------------------------------------


class NotificationInboxView(LoginRequiredMixin, ListView):
    """In-app notification feed scoped to the current user.

    Mirrors the mobile app's NotificationsInboxScreen. Supports an unread-only
    toggle via `?unread=1` and a Mark-all-read POST action.
    """

    model = Notification
    template_name = "portal/notifications.html"
    paginate_by = 50
    context_object_name = "notifications"

    def get_queryset(self):
        qs = Notification.objects.filter(user=self.request.user).select_related(
            "related_ticket"
        )
        if self.request.GET.get("unread") == "1":
            qs = qs.filter(read=False)
        return qs.order_by("-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "notifications"
        ctx["unread_count"] = Notification.objects.filter(
            user=self.request.user, read=False
        ).count()
        ctx["unread_only"] = self.request.GET.get("unread") == "1"
        return ctx


class NotificationMarkReadView(LoginRequiredMixin, View):
    """POST: mark a single notification read, then redirect."""

    def post(self, request, pk):
        notif = get_object_or_404(Notification, pk=pk, user=request.user)
        notif.read = True
        notif.save(update_fields=["read"])
        next_url = request.POST.get("next") or ""
        if notif.related_ticket_id:
            return redirect("portal:ticket_detail", pk=notif.related_ticket_id)
        return redirect(next_url or "portal:notifications")


class NotificationMarkAllReadView(LoginRequiredMixin, View):
    """POST: mark every unread notification for this user as read."""

    def post(self, request):
        Notification.objects.filter(user=request.user, read=False).update(read=True)
        messages.success(request, "Marked all notifications read.")
        return redirect("portal:notifications")


# ---------------------------------------------------------------------
# Audit log (admin only)
# ---------------------------------------------------------------------


class AuditLogListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = "portal/audit_log.html"
    paginate_by = 100
    context_object_name = "entries"

    def test_func(self) -> bool:
        u = self.request.user
        return bool(
            u.is_authenticated and (u.is_superuser or getattr(u, "is_admin_role", False))
        )

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied

    def get_queryset(self):
        from audit.models import AuditLog

        qs = AuditLog.objects.select_related("actor", "target_ct")
        actor = self.request.GET.get("actor")
        action = self.request.GET.get("action")
        if actor:
            qs = qs.filter(actor__email__icontains=actor)
        if action:
            qs = qs.filter(action__icontains=action)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "audit"
        ctx["filters"] = {
            "actor": self.request.GET.get("actor", ""),
            "action": self.request.GET.get("action", ""),
        }
        return ctx
