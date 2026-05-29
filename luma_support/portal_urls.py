"""Server-rendered web portal routes (Django templates)."""
from django.contrib.auth.views import LogoutView
from django.urls import path
from django.views.generic import RedirectView

from billing import portal_urls as billing_portal_urls
from leads import portal_urls as leads_portal_urls
from luma_support import portal_views as views
from quotes import portal_urls as quotes_portal_urls
from social import portal_urls as social_portal_urls

app_name = "portal"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="portal:dashboard", permanent=False)),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page="portal:login"), name="logout"),
    # 2FA mid-login (after password, before session is granted)
    path("2fa/setup/", views.TotpSetupView.as_view(), name="totp_setup"),
    path("2fa/verify/", views.TotpVerifyView.as_view(), name="totp_verify"),
    path("2fa/qr.svg", views.TotpQrView.as_view(), name="totp_qr"),
    path("2fa/recovery-codes/", views.RecoveryCodesView.as_view(), name="recovery_codes"),
    path("sessions/", views.SessionsView.as_view(), name="sessions"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    # Tickets
    path("tickets/", views.TicketListView.as_view(), name="ticket_list"),
    path(
        "tickets/board/",
        views.TicketBoardView.as_view(),
        name="ticket_board",
    ),
    path(
        "tickets/sla-analytics/",
        views.SlaAnalyticsView.as_view(),
        name="sla_analytics",
    ),
    path("tickets/new/", views.TicketCreateView.as_view(), name="ticket_create"),
    path("tickets/<int:pk>/", views.TicketDetailView.as_view(), name="ticket_detail"),
    path(
        "tickets/<int:pk>/status/",
        views.TicketStatusUpdateView.as_view(),
        name="ticket_status",
    ),
    path(
        "tickets/<int:pk>/log-time/",
        views.TimeEntryCreateView.as_view(),
        name="time_log",
    ),
    path(
        "tickets/<int:pk>/note/",
        views.TicketNoteCreateView.as_view(),
        name="ticket_note",
    ),
    path(
        "tickets/<int:pk>/draft-reply/",
        views.TicketDraftReplyView.as_view(),
        name="ticket_draft_reply",
    ),
    path(
        "tickets/bulk/",
        views.TicketBulkActionView.as_view(),
        name="ticket_bulk",
    ),
    path(
        "tickets/saved-filters/save/",
        views.SavedTicketFilterCreateView.as_view(),
        name="ticket_filter_save",
    ),
    path(
        "tickets/saved-filters/<int:pk>/delete/",
        views.SavedTicketFilterDeleteView.as_view(),
        name="ticket_filter_delete",
    ),
    path(
        "tickets/<int:pk>/merge/",
        views.TicketMergeView.as_view(),
        name="ticket_merge",
    ),
    # Clients
    path("clients/", views.ClientListView.as_view(), name="client_list"),
    path("clients/new/", views.ClientCreateView.as_view(), name="client_create"),
    path("clients/<int:pk>/", views.ClientDetailView.as_view(), name="client_detail"),
    path(
        "clients/<int:pk>/edit/",
        views.ClientUpdateView.as_view(),
        name="client_edit",
    ),
    path(
        "clients/<int:pk>/timeline/",
        views.ClientTimelineView.as_view(),
        name="client_timeline",
    ),
    path(
        "clients/<int:pk>/report.pdf",
        views.ClientMonthlyReportView.as_view(),
        name="client_monthly_report",
    ),
    path(
        "onboarding/<int:pk>/toggle/",
        views.OnboardingToggleView.as_view(),
        name="onboarding_toggle",
    ),
    # Contacts
    path(
        "clients/<int:client_pk>/contacts/new/",
        views.ContactCreateView.as_view(),
        name="contact_create",
    ),
    path(
        "contacts/<int:pk>/edit/",
        views.ContactUpdateView.as_view(),
        name="contact_edit",
    ),
    path(
        "contacts/<int:pk>/delete/",
        views.ContactDeleteView.as_view(),
        name="contact_delete",
    ),
    # Knowledge
    path("kb/", views.ArticleListView.as_view(), name="kb_list"),
    path("kb/gaps/", views.KbGapsReportView.as_view(), name="kb_gaps"),
    path("kb/<slug:slug>/", views.ArticleDetailView.as_view(), name="kb_detail"),
    path(
        "kb/<slug:slug>/history/",
        views.ArticleHistoryView.as_view(),
        name="kb_history",
    ),
    # Site visits (staff only)
    path(
        "site-visits/",
        views.SiteVisitListView.as_view(),
        name="site_visit_list",
    ),
    # Maintenance schedules (staff only)
    path(
        "schedules/",
        views.MaintenanceScheduleListView.as_view(),
        name="schedule_list",
    ),
    path(
        "schedules/new/",
        views.MaintenanceScheduleCreateView.as_view(),
        name="schedule_create",
    ),
    path(
        "schedules/<int:pk>/edit/",
        views.MaintenanceScheduleUpdateView.as_view(),
        name="schedule_edit",
    ),
    path(
        "schedules/<int:pk>/delete/",
        views.MaintenanceScheduleDeleteView.as_view(),
        name="schedule_delete",
    ),
    # CSAT (public, tokenized — no auth)
    path("csat/<str:token>/", views.CsatSubmitView.as_view(), name="csat_submit"),
    # Public per-client status page (opt-in via Client.status_page_slug).
    path(
        "status/<slug:slug>/",
        views.PublicStatusPageView.as_view(),
        name="status_page",
    ),
    # Client-facing: your systems with health status
    path("my-services/", views.MyServicesView.as_view(), name="my_services"),
    # Notifications inbox (in-app feed, parity with mobile)
    path(
        "notifications/",
        views.NotificationInboxView.as_view(),
        name="notifications",
    ),
    path(
        "notifications/<int:pk>/read/",
        views.NotificationMarkReadView.as_view(),
        name="notification_mark_read",
    ),
    path(
        "notifications/mark-all-read/",
        views.NotificationMarkAllReadView.as_view(),
        name="notifications_mark_all_read",
    ),
    # Audit log (admin only)
    path("audit/", views.AuditLogListView.as_view(), name="audit_log"),
    # Billing (admin only — gating enforced inside the views)
    *billing_portal_urls.urlpatterns,
    # Social (staff only — gating enforced inside the views)
    *social_portal_urls.urlpatterns,
    # Leads (staff only — gating enforced inside the views)
    *leads_portal_urls.urlpatterns,
    # Quotes (staff only + public /q/<token>/ accept link)
    *quotes_portal_urls.urlpatterns,
]
