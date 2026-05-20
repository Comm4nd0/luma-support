"""Recurring-revenue analytics.

Pure read-side helpers — no new models. `current_mrr()` is "what we're
billing right now" derived from each Client's `monthly_fee` plus an
active care plan. `mrr_history()` is the audited historical view,
derived from CONTRACT invoices keyed by `period_start` month, so it
reflects whatever actually went out the door (including referral
credits applied to the invoice).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable

from django.db.models import Sum
from django.utils import timezone

from clients.models import CarePlanTier, Client

from .models import Invoice


# -----------------------------------------------------------------
# Current state
# -----------------------------------------------------------------


def current_mrr() -> Decimal:
    """Sum monthly_fee across clients with an active care plan today."""
    today = timezone.localdate()
    qs = (
        Client.objects.exclude(care_plan_tier=CarePlanTier.NONE)
        .exclude(monthly_fee__isnull=True)
        .filter(monthly_fee__gt=0)
    )
    qs = qs.filter(
        # care_plan_renewal nullable → treat null as "still active".
        # If renewal date is set and in the past, exclude.
        models_q_active_renewal(today)
    )
    return qs.aggregate(total=Sum("monthly_fee"))["total"] or Decimal("0")


def models_q_active_renewal(today):
    """Q expression: care_plan_renewal is NULL or in the future."""
    from django.db.models import Q

    return Q(care_plan_renewal__isnull=True) | Q(care_plan_renewal__gte=today)


def arr() -> Decimal:
    return current_mrr() * Decimal("12")


def mrr_by_tier() -> dict[str, Decimal]:
    """MRR split by care-plan tier."""
    today = timezone.localdate()
    rows = (
        Client.objects.exclude(care_plan_tier=CarePlanTier.NONE)
        .filter(monthly_fee__gt=0)
        .filter(models_q_active_renewal(today))
        .values("care_plan_tier")
        .annotate(total=Sum("monthly_fee"))
    )
    return {r["care_plan_tier"]: r["total"] or Decimal("0") for r in rows}


# -----------------------------------------------------------------
# Historical buckets
# -----------------------------------------------------------------


@dataclass
class MonthBucket:
    month: date  # 1st of the month
    mrr: Decimal = Decimal("0")
    new_mrr: Decimal = Decimal("0")
    expansion_mrr: Decimal = Decimal("0")
    contraction_mrr: Decimal = Decimal("0")
    churn_mrr: Decimal = Decimal("0")
    active_clients: int = 0
    churned_clients: list[int] = field(default_factory=list)

    @property
    def net_new_mrr(self) -> Decimal:
        return (
            self.new_mrr + self.expansion_mrr
            - self.contraction_mrr - self.churn_mrr
        )


def _first_of_month(d: date) -> date:
    return d.replace(day=1)


def _shift_months(d: date, n: int) -> date:
    """Add `n` months (negative = past) to `d`, clamping to first-of-month."""
    total = d.year * 12 + (d.month - 1) + n
    year, month = divmod(total, 12)
    return date(year, month + 1, 1)


def mrr_history(months: int = 12) -> list[MonthBucket]:
    """Per-month MRR for the last `months` months, with movement breakdown.

    Movement classification per client per month:
    - new: had no MRR in the prior month, has MRR now
    - expansion: total went up vs the prior month
    - contraction: total went down (but still >0) vs the prior month
    - churn: had MRR last month, has none this month
    """
    today = _first_of_month(timezone.localdate())
    start = _shift_months(today, -(months - 1))

    qs = (
        Invoice.objects.filter(
            kind=Invoice.Kind.CONTRACT,
            period_start__gte=start,
            period_start__lte=today,
        )
        .values("client_id", "period_start")
        .annotate(total=Sum("total"))
        .order_by("period_start", "client_id")
    )

    # per_month: {first_of_month: {client_id: total}}
    per_month: dict[date, dict[int, Decimal]] = {}
    for row in qs:
        m = _first_of_month(row["period_start"])
        per_month.setdefault(m, {})[row["client_id"]] = row["total"] or Decimal(
            "0"
        )

    out: list[MonthBucket] = []
    prev: dict[int, Decimal] = {}
    cursor = start
    for _ in range(months):
        month_totals = per_month.get(cursor, {})
        bucket = MonthBucket(month=cursor)
        all_client_ids = set(month_totals) | set(prev)
        for cid in all_client_ids:
            now = month_totals.get(cid, Decimal("0"))
            then = prev.get(cid, Decimal("0"))
            if now > 0 and then == 0:
                bucket.new_mrr += now
            elif now == 0 and then > 0:
                bucket.churn_mrr += then
                bucket.churned_clients.append(cid)
            elif now > then:
                bucket.expansion_mrr += now - then
            elif now < then and now > 0:
                bucket.contraction_mrr += then - now
            bucket.mrr += now
            if now > 0:
                bucket.active_clients += 1
        out.append(bucket)
        prev = month_totals
        cursor = _shift_months(cursor, 1)
    return out


def gross_churn_rate(window_days: int = 90) -> Decimal:
    """Fraction of MRR lost over the trailing window. 0 → 1.

    Computed against the MRR at the start of the window.
    """
    today = _first_of_month(timezone.localdate())
    months = max(1, (window_days // 30))
    history = mrr_history(months=months + 1)
    if len(history) < 2:
        return Decimal("0")
    start_mrr = history[0].mrr
    if start_mrr <= 0:
        return Decimal("0")
    total_churn = sum(
        (b.churn_mrr for b in history[1:]), Decimal("0")
    )
    return (total_churn / start_mrr).quantize(Decimal("0.0001"))


def net_revenue_retention(months: int = 12) -> Decimal:
    """NRR over `months`: ending MRR from existing clients / starting MRR.

    A value of 1.10 (110%) means existing clients now pay 10% more than
    they did at the start of the window — expansion overcame churn.
    """
    history = mrr_history(months=months)
    if not history:
        return Decimal("0")
    start_mrr = history[0].mrr
    if start_mrr <= 0:
        return Decimal("0")
    end_mrr = history[-1].mrr
    # Subtract MRR coming from genuinely new clients in the window so we
    # measure same-cohort retention.
    new_in_window = sum(
        (b.new_mrr for b in history[1:]), Decimal("0")
    )
    same_cohort_end = max(end_mrr - new_in_window, Decimal("0"))
    return (same_cohort_end / start_mrr).quantize(Decimal("0.0001"))
