from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("invoices", views.InvoiceViewSet, basename="invoice")
router.register("payments", views.PaymentViewSet, basename="payment")

urlpatterns = router.urls
