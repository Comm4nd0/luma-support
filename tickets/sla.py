"""SLA computation policy.

Response targets, by priority:
    critical = 2 hours
    high     = 4 hours
    medium   = 24 hours
    low      = 48 hours

Auto-priority by client care plan tier (when caller didn't specify):
    enterprise   -> high
    professional -> medium
    essential    -> medium
    none         -> low
"""
from datetime import timedelta

PRIORITY_SLA = {
    "critical": timedelta(hours=2),
    "high": timedelta(hours=4),
    "medium": timedelta(hours=24),
    "low": timedelta(hours=48),
}

CARE_PLAN_PRIORITY = {
    "enterprise": "high",
    "professional": "medium",
    "essential": "medium",
    "none": "low",
}


def deadline_for(created_at, priority: str):
    return created_at + PRIORITY_SLA[priority]


def auto_priority_for(care_plan_tier: str) -> str:
    return CARE_PLAN_PRIORITY.get(care_plan_tier, "low")
