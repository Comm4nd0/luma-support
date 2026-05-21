import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0010_client_stripe_customer_id"),
        ("tickets", "0008_ticket_ai_summary"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="IngestEndpoint",
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
                ("name", models.CharField(max_length=80, unique=True)),
                ("token", models.CharField(max_length=64, unique=True)),
                (
                    "default_priority",
                    models.CharField(
                        choices=[
                            ("critical", "Critical"),
                            ("high", "High"),
                            ("medium", "Medium"),
                            ("low", "Low"),
                        ],
                        default="medium",
                        max_length=16,
                    ),
                ),
                (
                    "subject_field",
                    models.CharField(
                        default="title",
                        help_text="JSON key in the inbound body to use as the ticket subject.",
                        max_length=64,
                    ),
                ),
                (
                    "body_field",
                    models.CharField(
                        default="message",
                        help_text="JSON key for the ticket description (falls back to full payload).",
                        max_length=64,
                    ),
                ),
                ("last_called_at", models.DateTimeField(blank=True, null=True)),
                ("last_status", models.CharField(blank=True, max_length=32)),
                ("enabled", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ingest_endpoints",
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
            ],
            options={
                "ordering": ["name"],
            },
        ),
    ]
