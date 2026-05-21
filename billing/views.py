from rest_framework import mixins, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from clients.models import Client

from . import metrics
from .models import Invoice, Payment, XeroConnection
from .permissions import IsAdmin
from .serializers import InvoiceSerializer, PaymentSerializer
from .services import generate_time_invoice


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdmin])
def revenue_metrics(request):
    """Admin-only revenue snapshot for the mobile dashboard."""
    history = metrics.mrr_history(months=12)
    return Response(
        {
            "current_mrr": str(metrics.current_mrr()),
            "arr": str(metrics.arr()),
            "mrr_by_tier": {
                k: str(v) for k, v in metrics.mrr_by_tier().items()
            },
            "gross_churn_90d": str(metrics.gross_churn_rate(window_days=90)),
            "nrr_12mo": str(metrics.net_revenue_retention(months=12)),
            "history": [
                {
                    "month": b.month.isoformat(),
                    "mrr": str(b.mrr),
                    "new": str(b.new_mrr),
                    "expansion": str(b.expansion_mrr),
                    "contraction": str(b.contraction_mrr),
                    "churn": str(b.churn_mrr),
                    "active": b.active_clients,
                }
                for b in history
            ],
        }
    )


# Manual transitions the API permits. Anything else (e.g. → paid) is owned
# by Xero/payment-sync and shouldn't be forced from a client.
_ALLOWED_STATUS_TRANSITIONS = {
    Invoice.Status.DRAFT: {Invoice.Status.SENT, Invoice.Status.VOIDED},
    Invoice.Status.SENT: {Invoice.Status.VOIDED},
}


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.select_related("client").prefetch_related("lines")
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    filterset_fields = ["client", "kind", "status"]
    search_fields = ["client__name", "xero_invoice_id", "notes"]
    ordering_fields = ["created_at", "total", "due_date"]

    def perform_create(self, serializer):
        # Manual creates are always one-off drafts. Contract invoices come
        # from the monthly scheduled task; time-based ones from the
        # `generate_from_time` action below.
        serializer.save(created_by=self.request.user, kind=Invoice.Kind.ONE_OFF)

    def update(self, request, *args, **kwargs):
        if self.get_object().status != Invoice.Status.DRAFT:
            raise ValidationError(
                {"detail": "Only draft invoices can be edited."}
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if self.get_object().status != Invoice.Status.DRAFT:
            raise ValidationError(
                {"detail": "Only draft invoices can be deleted."}
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def send(self, request, pk=None):
        from .tasks import push_invoice_to_xero

        invoice = self.get_object()
        if invoice.xero_invoice_id:
            return Response({"detail": "already pushed"}, status=400)
        if not XeroConnection.objects.exists():
            return Response({"detail": "Xero is not connected"}, status=400)
        push_invoice_to_xero.delay(invoice.pk, "AUTHORISED")
        return Response({"detail": "queued"}, status=202)

    @action(detail=True, methods=["post"], url_path="status")
    def set_status(self, request, pk=None):
        invoice = self.get_object()
        target = request.data.get("status")
        if target not in dict(Invoice.Status.choices):
            return Response(
                {"detail": "unknown status"}, status=400
            )
        allowed = _ALLOWED_STATUS_TRANSITIONS.get(invoice.status, set())
        if target not in allowed:
            return Response(
                {
                    "detail": (
                        f"cannot transition from {invoice.status} to {target}"
                    )
                },
                status=400,
            )
        invoice.status = target
        update_fields = ["status", "updated_at"]
        if target == Invoice.Status.SENT and invoice.sent_at is None:
            from django.utils import timezone

            invoice.sent_at = timezone.now()
            update_fields.append("sent_at")
        invoice.save(update_fields=update_fields)
        return Response(InvoiceSerializer(invoice).data, status=200)

    @action(detail=False, methods=["post"], url_path="generate-from-time")
    def generate_from_time(self, request):
        client_id = request.data.get("client")
        if client_id is None:
            return Response({"detail": "client is required"}, status=400)
        try:
            client = Client.objects.get(pk=client_id)
        except Client.DoesNotExist:
            return Response({"detail": "client not found"}, status=404)
        invoice = generate_time_invoice(client)
        if invoice is None:
            return Response(
                {"detail": "no unbilled time entries for this client"},
                status=400,
            )
        return Response(InvoiceSerializer(invoice).data, status=201)


class PaymentViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    queryset = Payment.objects.select_related("invoice").all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    filterset_fields = ["invoice"]
    ordering_fields = ["paid_at", "amount"]


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def stripe_customer_portal_session(request):
    """Return a one-shot Stripe Customer Portal URL.

    Body: ``{"client": <id>, "return_url": "<url>"}``. Admins can open
    any client's portal; non-admin client users can only open their own
    account's portal. Returns ``{"url": null}`` when Stripe isn't
    configured so the calling UI can hide the button gracefully.
    """
    from .stripe_client import create_customer_portal_session, is_configured

    client_id = request.data.get("client")
    return_url = request.data.get("return_url") or ""
    if not client_id or not return_url:
        raise ValidationError({"detail": "client and return_url are required"})

    try:
        client = Client.objects.get(pk=client_id)
    except Client.DoesNotExist:
        return Response({"detail": "client not found"}, status=404)

    user = request.user
    if not user.can_view_all and user.client_id != client.pk:
        return Response({"detail": "forbidden"}, status=403)

    if not is_configured():
        return Response({"url": None})

    url = create_customer_portal_session(client, return_url)
    return Response({"url": url})
