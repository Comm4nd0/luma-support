from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0009_ingest_endpoint"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticket",
            name="client_last_viewed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
