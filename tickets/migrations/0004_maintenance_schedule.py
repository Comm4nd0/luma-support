import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0001_initial"),
        ("tickets", "0003_csat_response"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MaintenanceSchedule",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "cadence",
                    models.CharField(
                        choices=[
                            ("weekly", "Weekly"),
                            ("monthly", "Monthly"),
                            ("quarterly", "Quarterly"),
                            ("biannual", "Every 6 months"),
                            ("annual", "Annual"),
                        ],
                        max_length=16,
                    ),
                ),
                ("next_run_at", models.DateField()),
                ("template_subject", models.CharField(max_length=300)),
                ("template_description", models.TextField(blank=True)),
                (
                    "priority",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("critical", "Critical"),
                            ("high", "High"),
                            ("medium", "Medium"),
                            ("low", "Low"),
                        ],
                        max_length=16,
                    ),
                ),
                ("active", models.BooleanField(default=True)),
                ("last_run_at", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="maintenance_schedules",
                        to="clients.client",
                    ),
                ),
                (
                    "default_assignee",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "system",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="maintenance_schedules",
                        to="clients.system",
                    ),
                ),
            ],
            options={
                "ordering": ["next_run_at", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="maintenanceschedule",
            index=models.Index(
                fields=["active", "next_run_at"],
                name="tickets_mai_active_8b4a08_idx",
            ),
        ),
    ]
