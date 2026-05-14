"""Server-rendered web portal routes (Django templates)."""
from django.contrib.auth.views import LogoutView
from django.urls import path
from django.views.generic import RedirectView

from billing import portal_urls as billing_portal_urls
from luma_support import portal_views as views

app_name = "portal"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="portal:dashboard", permanent=False)),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page="portal:login"), name="logout"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    # Tickets
    path("tickets/", views.TicketListView.as_view(), name="ticket_list"),
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
    # Clients
    path("clients/", views.ClientListView.as_view(), name="client_list"),
    path("clients/new/", views.ClientCreateView.as_view(), name="client_create"),
    path("clients/<int:pk>/", views.ClientDetailView.as_view(), name="client_detail"),
    path(
        "clients/<int:pk>/edit/",
        views.ClientUpdateView.as_view(),
        name="client_edit",
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
    path("kb/<slug:slug>/", views.ArticleDetailView.as_view(), name="kb_detail"),
    # Billing (admin only — gating enforced inside the views)
    *billing_portal_urls.urlpatterns,
]
