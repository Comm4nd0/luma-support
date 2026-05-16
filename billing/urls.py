from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views
from .webhooks import StripeWebhookView

router = DefaultRouter()
router.register("invoices", views.InvoiceViewSet, basename="invoice")
router.register("payments", views.PaymentViewSet, basename="payment")

urlpatterns = router.urls + [
    path("webhooks/stripe/", StripeWebhookView.as_view(), name="stripe-webhook"),
]
