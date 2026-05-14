from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Invoice, Payment, XeroConnection
from .permissions import IsAdmin
from .serializers import InvoiceSerializer, PaymentSerializer


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.select_related("client").prefetch_related("lines")
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    filterset_fields = ["client", "kind", "status"]
    search_fields = ["client__name", "xero_invoice_id", "notes"]
    ordering_fields = ["created_at", "total", "due_date"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, kind=Invoice.Kind.ONE_OFF)

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


class PaymentViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    queryset = Payment.objects.select_related("invoice").all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    filterset_fields = ["invoice"]
    ordering_fields = ["paid_at", "amount"]
