"""Stripe webhook handler.

Signature is verified via `billing.stripe_client.verify_webhook`. We
handle `checkout.session.completed` as the primary "paid" signal, with
`payment_intent.succeeded` as a backup path. Both routes write Payment
rows keyed on `stripe_payment_intent_id` for idempotent replays.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.utils import timezone
from rest_framework import permissions, views
from rest_framework.response import Response

from .models import Invoice, Payment
from .stripe_client import verify_webhook

logger = logging.getLogger(__name__)


class StripeWebhookView(views.APIView):
    """POST /api/v1/billing/webhooks/stripe/ — public, signature-verified."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
        try:
            event = verify_webhook(request.body, sig_header)
        except ValueError:
            logger.warning("Stripe webhook: invalid signature or no secret")
            return Response({"detail": "invalid signature"}, status=400)
        except Exception:
            logger.exception("Stripe webhook: unexpected verify failure")
            return Response({"detail": "invalid"}, status=400)

        event_type = event.get("type") if isinstance(event, dict) else event["type"]
        handler = {
            "checkout.session.completed": self._on_checkout_session_completed,
            "payment_intent.succeeded": self._on_payment_intent_succeeded,
        }.get(event_type)
        if handler is not None:
            try:
                handler(event)
            except Exception:
                logger.exception("Stripe webhook handler failed for %s", event_type)
                # Tell Stripe to retry.
                return Response({"detail": "handler error"}, status=500)
        return Response({"received": True}, status=200)

    # ----- handlers ---------------------------------------------------

    def _on_checkout_session_completed(self, event):
        session = event["data"]["object"]
        meta = session.get("metadata") or {}
        invoice_id = meta.get("invoice_id")
        pi = session.get("payment_intent")
        if not invoice_id or not pi:
            return
        invoice = self._lookup_invoice(invoice_id)
        if invoice is None:
            return
        amount = Decimal(str(session.get("amount_total", 0))) / Decimal(100)
        self._record_payment(invoice, pi, amount, reference=session.get("id", ""))

    def _on_payment_intent_succeeded(self, event):
        pi = event["data"]["object"]
        meta = pi.get("metadata") or {}
        invoice_id = meta.get("invoice_id")
        if not invoice_id:
            return
        invoice = self._lookup_invoice(invoice_id)
        if invoice is None:
            return
        amount = Decimal(str(pi.get("amount", 0))) / Decimal(100)
        self._record_payment(invoice, pi["id"], amount, reference=pi.get("id", ""))

    # ----- helpers ----------------------------------------------------

    @staticmethod
    def _lookup_invoice(invoice_id) -> Invoice | None:
        try:
            return Invoice.objects.get(pk=int(invoice_id))
        except (Invoice.DoesNotExist, ValueError, TypeError):
            return None

    @staticmethod
    def _record_payment(
        invoice: Invoice, payment_intent_id: str, amount: Decimal, reference: str
    ) -> None:
        Payment.objects.update_or_create(
            stripe_payment_intent_id=payment_intent_id,
            defaults={
                "invoice": invoice,
                "amount": amount,
                "paid_at": timezone.now(),
                "reference": reference or "",
            },
        )
        if invoice.status != Invoice.Status.PAID:
            invoice.status = Invoice.Status.PAID
            invoice.paid_at = timezone.now()
            invoice.save(update_fields=["status", "paid_at", "updated_at"])
