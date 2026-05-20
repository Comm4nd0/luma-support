from django.urls import path

from . import portal_views

urlpatterns = [
    path(
        "dashboard/revenue/",
        portal_views.RevenueDashboardView.as_view(),
        name="revenue_dashboard",
    ),
    path("billing/", portal_views.InvoiceListView.as_view(), name="invoice_list"),
    path(
        "billing/invoices/new/",
        portal_views.InvoiceCreateView.as_view(),
        name="invoice_create",
    ),
    path(
        "billing/invoices/<int:pk>/",
        portal_views.InvoiceDetailView.as_view(),
        name="invoice_detail",
    ),
    path(
        "billing/invoices/<int:pk>/edit/",
        portal_views.InvoiceUpdateView.as_view(),
        name="invoice_edit",
    ),
    path(
        "clients/<int:pk>/invoices/generate-time/",
        portal_views.ClientGenerateTimeInvoiceView.as_view(),
        name="client_generate_time_invoice",
    ),
    path(
        "settings/xero/",
        portal_views.XeroSettingsView.as_view(),
        name="xero_settings",
    ),
    path(
        "billing/invoices/<int:pk>/send/",
        portal_views.InvoiceSendView.as_view(),
        name="invoice_send",
    ),
    path(
        "billing/xero/connect/",
        portal_views.XeroConnectView.as_view(),
        name="xero_connect",
    ),
    path(
        "billing/xero/oauth/callback/",
        portal_views.XeroOAuthCallbackView.as_view(),
        name="xero_oauth_callback",
    ),
    path(
        "billing/xero/disconnect/",
        portal_views.XeroDisconnectView.as_view(),
        name="xero_disconnect",
    ),
]
