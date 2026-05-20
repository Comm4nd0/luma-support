"""Per-client health score.

Pure derivation — no stored fields. Lets `clients_at_risk()` stay
honest even after a CSAT lands or a system flips DOWN. The score is a
weighted blend of four signals:

- CSAT rolling 90-day average        — 40%
- Open ticket volume vs 90-day avg   — 20%
- Outstanding overdue invoices       — 20%
- Fraction of systems reporting OK   — 20%

Score is on a 0-100 scale where 100 is "everything is wonderful". Bands:

- 75+   → "good"   (green)
- 50-74 → "watch"  (amber)
- <50   → "at risk" (red)

Callers asking about many clients at once should use `score_clients()`
to batch the trailing-window queries.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Iterable

from django.db.models import Avg, Count, Q
from django.utils import timezone

from .models import Client, HealthStatus


@dataclass
class HealthScore:
    client_id: int
    score: int  # 0..100
    band: str  # "good" | "watch" | "at_risk"
    csat: float | None  # average rating 1-5, None if no data
    open_tickets: int
    overdue_invoices: int
    systems_ok_pct: float | None
    reasons: list[str]


# Cut-points and weights — exposed for testing.
WEIGHT_CSAT = 0.40
WEIGHT_TICKETS = 0.20
WEIGHT_PAYMENTS = 0.20
WEIGHT_SYSTEMS = 0.20

BAND_GOOD = 75
BAND_WATCH = 50


def _band(score: int) -> str:
    if score >= BAND_GOOD:
        return "good"
    if score >= BAND_WATCH:
        return "watch"
    return "at_risk"


def score_client(client: Client) -> HealthScore:
    """Compute a single client's health snapshot."""
    return score_clients([client])[0]


def score_clients(clients: Iterable[Client]) -> list[HealthScore]:
    """Compute health for a batch of clients with a small number of queries."""
    from billing.models import Invoice
    from tickets.models import CsatResponse, Ticket

    now = timezone.now()
    today = timezone.localdate()
    window = now - timedelta(days=90)

    clients = list(clients)
    ids = [c.pk for c in clients]
    if not ids:
        return []

    # --- CSAT (avg rating over last 90 days, scaled to 0..100) ----------
    csat_rows = (
        CsatResponse.objects.filter(
            ticket__client_id__in=ids,
            responded_at__gte=window,
            rating__isnull=False,
        )
        .values("ticket__client_id")
        .annotate(avg=Avg("rating"), n=Count("id"))
    )
    csat_by_client = {
        r["ticket__client_id"]: (r["avg"], r["n"]) for r in csat_rows
    }

    # --- Open tickets right now ------------------------------------------
    open_rows = (
        Ticket.objects.exclude(
            status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED]
        )
        .filter(client_id__in=ids)
        .values("client_id")
        .annotate(n=Count("id"))
    )
    open_by_client = {r["client_id"]: r["n"] for r in open_rows}

    # --- Recent ticket volume (last 90d) — used to normalise -------------
    recent_rows = (
        Ticket.objects.filter(client_id__in=ids, created_at__gte=window)
        .values("client_id")
        .annotate(n=Count("id"))
    )
    recent_by_client = {r["client_id"]: r["n"] for r in recent_rows}

    # --- Overdue invoices ------------------------------------------------
    overdue_rows = (
        Invoice.objects.filter(
            client_id__in=ids,
            status__in=[Invoice.Status.SENT, Invoice.Status.AUTHORISED],
            due_date__lt=today,
        )
        .values("client_id")
        .annotate(n=Count("id"))
    )
    overdue_by_client = {r["client_id"]: r["n"] for r in overdue_rows}

    # --- Systems health: pct reporting OK -------------------------------
    system_rows = (
        Client.objects.filter(pk__in=ids)
        .values("pk")
        .annotate(
            total=Count("systems"),
            ok=Count(
                "systems", filter=Q(systems__health_status=HealthStatus.OK)
            ),
        )
    )
    systems_by_client = {
        r["pk"]: (r["total"], r["ok"]) for r in system_rows
    }

    out: list[HealthScore] = []
    for client in clients:
        csat_avg, _csat_n = csat_by_client.get(client.pk, (None, 0))
        open_n = open_by_client.get(client.pk, 0)
        recent_n = recent_by_client.get(client.pk, 0)
        overdue_n = overdue_by_client.get(client.pk, 0)
        total_systems, ok_systems = systems_by_client.get(client.pk, (0, 0))

        reasons: list[str] = []
        weight_sum = Decimal("0")
        score_acc = Decimal("0")

        # CSAT: missing data → neutral 75. Tuned so a single 3/5 doesn't tank.
        if csat_avg is not None:
            csat_norm = (Decimal(str(csat_avg)) - 1) / 4  # 1..5 → 0..1
            csat_score = csat_norm * 100
            if csat_avg < 3:
                reasons.append(f"CSAT averaging {csat_avg:.1f}/5")
        else:
            csat_score = Decimal("75")
        score_acc += csat_score * Decimal(str(WEIGHT_CSAT))
        weight_sum += Decimal(str(WEIGHT_CSAT))

        # Ticket volume: open vs trailing avg. >2× → penalty.
        avg_open = recent_n / 3.0 if recent_n else 0  # ~per-month
        if avg_open and open_n > 2 * avg_open:
            tickets_score = Decimal("40")
            reasons.append(
                f"{open_n} open vs ~{avg_open:.0f}/mo trailing"
            )
        elif open_n > 8:
            tickets_score = Decimal("50")
            reasons.append(f"{open_n} open tickets")
        else:
            tickets_score = Decimal("100")
        score_acc += tickets_score * Decimal(str(WEIGHT_TICKETS))
        weight_sum += Decimal(str(WEIGHT_TICKETS))

        # Payments: each overdue invoice costs ~30 points, floor 0.
        payments_score = max(Decimal("0"), Decimal("100") - Decimal(overdue_n) * Decimal("30"))
        if overdue_n:
            reasons.append(
                f"{overdue_n} overdue invoice{'s' if overdue_n != 1 else ''}"
            )
        score_acc += payments_score * Decimal(str(WEIGHT_PAYMENTS))
        weight_sum += Decimal(str(WEIGHT_PAYMENTS))

        # Systems: % OK
        systems_pct: float | None = None
        if total_systems:
            systems_pct = ok_systems / total_systems
            systems_score = Decimal(str(systems_pct)) * 100
            if systems_pct < 1:
                reasons.append(
                    f"{int(systems_pct * 100)}% systems OK"
                )
        else:
            systems_score = Decimal("75")  # neutral when nothing monitored
        score_acc += systems_score * Decimal(str(WEIGHT_SYSTEMS))
        weight_sum += Decimal(str(WEIGHT_SYSTEMS))

        final = int((score_acc / weight_sum).quantize(Decimal("1")))
        final = max(0, min(100, final))
        out.append(
            HealthScore(
                client_id=client.pk,
                score=final,
                band=_band(final),
                csat=float(csat_avg) if csat_avg is not None else None,
                open_tickets=open_n,
                overdue_invoices=overdue_n,
                systems_ok_pct=systems_pct,
                reasons=reasons,
            )
        )
    return out


def clients_at_risk(limit: int = 10) -> list[HealthScore]:
    """Lowest-scoring clients (at_risk or watch), bottom N first."""
    all_clients = list(Client.objects.all())
    scores = score_clients(all_clients)
    risky = [s for s in scores if s.band != "good"]
    risky.sort(key=lambda s: s.score)
    return risky[:limit]
