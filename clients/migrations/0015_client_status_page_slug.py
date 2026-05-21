from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0014_health_sample"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="status_page_slug",
            field=models.SlugField(blank=True, max_length=80, null=True, unique=True),
        ),
    ]
