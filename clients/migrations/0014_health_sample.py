import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0013_client_document"),
    ]

    operations = [
        migrations.CreateModel(
            name="HealthSample",
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
                ("metric", models.CharField(max_length=64)),
                ("value", models.FloatField()),
                ("sampled_at", models.DateTimeField(auto_now_add=True)),
                (
                    "system",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="health_samples",
                        to="clients.system",
                    ),
                ),
            ],
            options={
                "ordering": ["-sampled_at"],
            },
        ),
        migrations.AddIndex(
            model_name="healthsample",
            index=models.Index(
                fields=["system", "metric", "-sampled_at"],
                name="clients_hea_system__9a8c6f_idx",
            ),
        ),
    ]
