"""Anomaly detector — z-score against rolling baseline."""
from datetime import timedelta

import pytest
from django.utils import timezone

from clients.models import HealthSample, System, SystemType
from system.anomaly import detect_for_system, open_ticket_for, sweep
from tickets.models import Ticket

pytestmark = pytest.mark.django_db


def _add(system, metric, value, *, minutes_ago):
    """Insert a HealthSample at a precise timestamp."""
    s = HealthSample.objects.create(system=system, metric=metric, value=value)
    s.sampled_at = timezone.now() - timedelta(minutes=minutes_ago)
    s.save(update_fields=["sampled_at"])
    return s


def _seed_baseline(system, metric, value, *, count, start_minutes_ago):
    """Insert ``count`` historical samples ending at ``start_minutes_ago``."""
    for i in range(count):
        _add(system, metric, value, minutes_ago=start_minutes_ago + i)


def test_no_anomaly_when_latest_in_baseline(client_record):
    s = System.objects.create(client=client_record, name="x", type=SystemType.NETWORK)
    _seed_baseline(s, "cpu", 10.0, count=10, start_minutes_ago=5)
    # Latest sample sits at baseline mean — no spike.
    _add(s, "cpu", 10.0, minutes_ago=1)
    assert detect_for_system(s) == []


def test_anomaly_flagged_on_spike(client_record):
    s = System.objects.create(client=client_record, name="x", type=SystemType.NETWORK)
    # Slightly varied baseline so stddev is non-zero.
    for i, v in enumerate([10.0, 11.0, 12.0, 10.0, 11.0, 10.0, 9.0, 10.0, 11.0, 10.0]):
        _add(s, "cpu", v, minutes_ago=10 + i)
    # Latest sample is a clear outlier.
    _add(s, "cpu", 85.0, minutes_ago=1)
    anomalies = detect_for_system(s)
    assert len(anomalies) == 1
    assert anomalies[0].metric == "cpu"


def test_open_ticket_creates_low_priority_draft(client_record):
    from dataclasses import asdict

    from system.anomaly import Anomaly

    s = System.objects.create(client=client_record, name="x", type=SystemType.NETWORK)
    a = Anomaly(s.pk, "cpu", 85.0, 10.0, 1.0, 75.0)
    t = open_ticket_for(s, a)
    assert t is not None
    assert t.priority == "low"
    assert t.client == client_record
    assert "Anomaly" in t.subject


def test_open_ticket_dedupes_within_24h(client_record):
    from system.anomaly import Anomaly

    s = System.objects.create(client=client_record, name="x", type=SystemType.NETWORK)
    a = Anomaly(s.pk, "cpu", 85.0, 10.0, 1.0, 75.0)
    assert open_ticket_for(s, a) is not None
    # Second call within 24h: dedup → None.
    assert open_ticket_for(s, a) is None
    assert Ticket.objects.filter(client=client_record).count() == 1


def test_sweep_opens_tickets_across_all_systems(client_record):
    a = System.objects.create(client=client_record, name="A", type=SystemType.NETWORK)
    for i, v in enumerate([10.0, 11.0, 12.0, 10.0, 11.0, 10.0, 9.0, 10.0, 11.0, 10.0]):
        _add(a, "cpu", v, minutes_ago=10 + i)
    _add(a, "cpu", 85.0, minutes_ago=1)
    b = System.objects.create(client=client_record, name="B", type=SystemType.NETWORK)
    # B has too-few samples → skipped.
    for i in range(3):
        _add(b, "latency", 50.0, minutes_ago=i + 1)
    assert sweep() == 1
