"""Periodic upkeep for quotes."""
from celery import shared_task
from django.utils import timezone

from .models import Quote, QuoteStatus


@shared_task
def expire_stale_quotes():
    """Flip DRAFT/SENT quotes past their `valid_until` to EXPIRED."""
    today = timezone.localdate()
    qs = Quote.objects.filter(
        status__in=(QuoteStatus.DRAFT, QuoteStatus.SENT),
        valid_until__lt=today,
    )
    count = qs.update(status=QuoteStatus.EXPIRED, updated_at=timezone.now())
    return f"quote-expiry: {count} expired"
