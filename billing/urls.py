from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views
from .webhooks import StripeWebhookView

router = DefaultRouter()
router.register("invoices", views.InvoiceViewSet, basename="invoice")
router.register("payments", views.PaymentViewSet, basename="payment")
router.register("credit-notes", views.CreditNoteViewSet, basename="creditnote")

urlpatterns = router.urls + [
    path("webhooks/stripe/", StripeWebhookView.as_view(), name="stripe-webhook"),
    path("revenue/", views.revenue_metrics, name="revenue-metrics"),
    path(
        "portal-session/",
        views.stripe_customer_portal_session,
        name="stripe-portal-session",
    ),
]
