"""Seed the default onboarding-task templates.

Reversible — `unapply` clears the seed rows so the rollback doesn't
leave orphaned templates behind. Re-applying is idempotent because the
seed function checks for an existing row by title.
"""
from django.db import migrations


_DEFAULTS = [
    ("Send welcome email", 0, 1),
    ("Schedule kickoff call", 1, 3),
    ("Audit existing systems", 2, 7),
    ("Deploy monitoring", 3, 14),
    ("Issue first invoice", 4, 14),
    ("Schedule recurring maintenance", 5, 21),
]


def seed(apps, schema_editor):
    OnboardingTaskTemplate = apps.get_model("clients", "OnboardingTaskTemplate")
    for title, order, due_offset in _DEFAULTS:
        OnboardingTaskTemplate.objects.update_or_create(
            title=title,
            defaults={"order": order, "due_offset_days": due_offset},
        )


def unseed(apps, schema_editor):
    OnboardingTaskTemplate = apps.get_model("clients", "OnboardingTaskTemplate")
    OnboardingTaskTemplate.objects.filter(
        title__in=[t for t, _, _ in _DEFAULTS]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("clients", "0008_onboardingtasktemplate_clientonboardingtask"),
    ]

    operations = [migrations.RunPython(seed, unseed)]
