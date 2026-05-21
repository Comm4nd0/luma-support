import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0007_alter_notification_type"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OutboundWebhook",
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
                ("name", models.CharField(max_length=80)),
                ("url", models.URLField(max_length=500)),
                (
                    "format",
                    models.CharField(
                        choices=[
                            ("slack", "Slack-compatible (Discord too)"),
                            ("teams", "Microsoft Teams (Office 365 connector)"),
                            ("generic", "Generic JSON POST"),
                        ],
                        default="slack",
                        max_length=16,
                    ),
                ),
                (
                    "event_filter",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text=(
                            "List of Notification.Type values to forward. Leave "
                            "empty to forward every notification this user gets."
                        ),
                    ),
                ),
                ("enabled", models.BooleanField(default=True)),
                ("last_called_at", models.DateTimeField(blank=True, null=True)),
                ("last_status", models.CharField(blank=True, max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="outbound_webhooks",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
    ]
