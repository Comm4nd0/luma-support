import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("knowledge", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="KbSearchLog",
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
                ("query", models.CharField(max_length=500)),
                ("results_count", models.PositiveIntegerField(default=0)),
                (
                    "source",
                    models.CharField(
                        default="search",
                        help_text=(
                            '"search" for /articles/search/, "suggest" for '
                            "the AI-ranked draft helper."
                        ),
                        max_length=32,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
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
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="kbsearchlog",
            index=models.Index(
                fields=["-created_at"], name="knowledge_k_created_e7c14a_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="kbsearchlog",
            index=models.Index(
                fields=["results_count", "-created_at"],
                name="knowledge_k_results_82a0b6_idx",
            ),
        ),
    ]
