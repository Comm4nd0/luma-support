from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FeatureFlag",
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
                ("name", models.SlugField(max_length=64, unique=True)),
                ("description", models.CharField(blank=True, max_length=255)),
                (
                    "enabled",
                    models.BooleanField(
                        default=False,
                        help_text=(
                            "Master switch. When false the flag is off for everyone."
                        ),
                    ),
                ),
                (
                    "percentage",
                    models.PositiveSmallIntegerField(
                        default=100,
                        help_text=(
                            "0-100. When enabled=True, fraction of users that "
                            "see the feature. Bucketing is deterministic per "
                            "user id, so a given user always either sees or "
                            "doesn't see the feature for a given percentage."
                        ),
                    ),
                ),
                (
                    "allowed_users",
                    models.ManyToManyField(
                        blank=True,
                        help_text=(
                            "If non-empty, the flag is *only* on for these "
                            "users (ignores percentage). Use for staff-only "
                            "or pilot rollouts."
                        ),
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
    ]
