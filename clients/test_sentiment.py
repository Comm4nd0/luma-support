"""Negative-CSAT signal feeds into the health score breakdown."""
import pytest
from django.utils import timezone

from clients.health import score_client
from tickets.models import CsatResponse, Ticket

pytestmark = pytest.mark.django_db


def test_negative_csat_with_comment_adds_reason(client_record):
    for _ in range(2):
        t = Ticket.objects.create(client=client_record, subject="x")
        CsatResponse.objects.create(
            ticket=t, rating=2, comment="this is awful", responded_at=timezone.now()
        )
    score = score_client(client_record)
    assert any("negative CSAT" in r for r in score.reasons)


def test_low_rating_without_comment_does_not_count(client_record):
    t = Ticket.objects.create(client=client_record, subject="x")
    CsatResponse.objects.create(
        ticket=t, rating=2, comment="", responded_at=timezone.now()
    )
    score = score_client(client_record)
    # The avg < 3 reason still fires, but the negative-comment one
    # specifically should not.
    assert not any("negative CSAT comment" in r for r in score.reasons)
