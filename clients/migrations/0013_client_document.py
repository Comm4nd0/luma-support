import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import clients.models


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0012_site_visit"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ClientDocument",
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
                ("title", models.CharField(max_length=200)),
                (
                    "file",
                    models.FileField(
                        upload_to=clients.models._client_document_path
                    ),
                ),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("contract", "Contract"),
                            ("warranty", "Warranty"),
                            ("diagram", "Diagram"),
                            ("welcome", "Welcome pack"),
                            ("other", "Other"),
                        ],
                        default="other",
                        max_length=16,
                    ),
                ),
                (
                    "client_visible",
                    models.BooleanField(
                        default=True,
                        help_text=(
                            "Visible to the client's portal users. Disable "
                            "for internal docs."
                        ),
                    ),
                ),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documents",
                        to="clients.client",
                    ),
                ),
                (
                    "uploaded_by",
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
                "ordering": ["-uploaded_at"],
            },
        ),
    ]
