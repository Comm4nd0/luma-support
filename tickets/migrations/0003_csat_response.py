from django.db import migrations, models

import tickets.models


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0002_timeentry_invoice_line"),
    ]

    operations = [
        migrations.CreateModel(
            name="CsatResponse",
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
                    "token",
                    models.CharField(
                        default=tickets.models._csat_token,
                        max_length=64,
                        unique=True,
                    ),
                ),
                ("rating", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("comment", models.TextField(blank=True)),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
                (
                    "ticket",
                    models.OneToOneField(
                        on_delete=models.deletion.CASCADE,
                        related_name="csat",
                        to="tickets.ticket",
                    ),
                ),
            ],
            options={"ordering": ["-requested_at"]},
        ),
    ]
