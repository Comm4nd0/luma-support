from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0005_ticket_sla_paused_at"),
    ]

    operations = [
        migrations.CreateModel(
            name="TicketTag",
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
                ("name", models.CharField(max_length=64, unique=True)),
                ("slug", models.SlugField(max_length=64, unique=True)),
                (
                    "color",
                    models.CharField(
                        default="#14b8a6",
                        help_text="Hex colour with leading # — used to tint the pill.",
                        max_length=7,
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="ticket",
            name="tags",
            field=models.ManyToManyField(
                blank=True, related_name="tickets", to="tickets.tickettag"
            ),
        ),
    ]
