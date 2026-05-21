"""Light-touch anomaly detection on monitored system metrics.

Walks recent ``HealthSample`` rows per (system, metric) and flags any
that sit more than ``Z`` standard deviations from the rolling baseline.
A flagged anomaly opens a low-priority "investigate" draft ticket
assigned to the system's client, with the metric + value in the body
so Marco doesn't have to dig.

Deliberately simple — z-score over a rolling window. Promote to MAD /
EWMA later if signal-to-noise gets bad.
"""
from __future__ import annotations

import logging
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from typing import Iterable

from django.utils import timezone

from clients.models import HealthSample, System

logger = logging.getLogger(__name__)

# Tunables (kept module-local for now; promote to settings if Marco
# wants per-environment overrides).
WINDOW_SAMPLES = 30
MIN_SAMPLES = 10
Z_THRESHOLD = 3.0
NOTIFY_PRIORITY = "low"


@dataclass
class Anomaly:
    system_id: int
    metric: str
    value: float
    baseline_mean: float
    baseline_stddev: float
    z_score: float


def _stddev(values: Iterable[float]) -> float:
    values = list(values)
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    return math.sqrt(var)


def detect_for_system(system: System) -> list[Anomaly]:
    """Return any anomalies in this system's recent samples, per metric."""
    out: list[Anomaly] = []
    by_metric: dict[str, list[HealthSample]] = defaultdict(list)
    qs = (
        HealthSample.objects.filter(system=system)
        .order_by("-sampled_at")[: WINDOW_SAMPLES * 6]
    )
    for sample in qs:
        if len(by_metric[sample.metric]) < WINDOW_SAMPLES:
            by_metric[sample.metric].append(sample)
    for metric, samples in by_metric.items():
        if len(samples) < MIN_SAMPLES:
            continue
        latest = samples[0]
        baseline = [s.value for s in samples[1:]]
        if not baseline:
            continue
        mean = sum(baseline) / len(baseline)
        sd = _stddev(baseline)
        if sd == 0:
            # Constant baseline — flag only when latest != baseline mean.
            if latest.value != mean:
                out.append(
                    Anomaly(system.pk, metric, latest.value, mean, 0.0,
                            float("inf"))
                )
            continue
        z = abs(latest.value - mean) / sd
        if z >= Z_THRESHOLD:
            out.append(
                Anomaly(system.pk, metric, latest.value, mean, sd, z)
            )
    return out


def open_ticket_for(system: System, anomaly: Anomaly):
    """Open a draft investigation ticket for the supplied anomaly.

    Idempotent over the past 24h on a (system, metric, body-prefix) key:
    if we already opened a similar one recently, don't pile on.
    """
    from tickets.models import Ticket

    now = timezone.now()
    title = f"[Anomaly] {system.name} — {anomaly.metric} spike"
    body = (
        f"Most recent {anomaly.metric}: {anomaly.value:.2f}\n"
        f"Rolling baseline: mean={anomaly.baseline_mean:.2f}, "
        f"stddev={anomaly.baseline_stddev:.2f} "
        f"(z-score={anomaly.z_score:.1f}).\n\n"
        "Auto-opened by the anomaly detector."
    )
    recent = Ticket.objects.filter(
        client=system.client,
        system=system,
        subject=title,
        created_at__gte=now - timedelta(hours=24),
    ).exists()
    if recent:
        return None
    return Ticket.objects.create(
        client=system.client,
        system=system,
        subject=title,
        description=body,
        priority=NOTIFY_PRIORITY,
    )


def sweep() -> int:
    """Run the detector across every monitored System. Returns the
    number of tickets opened. Safe to wire to Celery beat."""
    opened = 0
    for system in System.objects.all():
        try:
            anomalies = detect_for_system(system)
        except Exception:
            logger.exception("anomaly sweep failed for system %s", system.pk)
            continue
        for anomaly in anomalies:
            if open_ticket_for(system, anomaly) is not None:
                opened += 1
    return opened
