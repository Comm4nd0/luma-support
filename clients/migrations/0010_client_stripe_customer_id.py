from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0009_seed_onboarding_templates"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="stripe_customer_id",
            field=models.CharField(blank=True, max_length=64),
        ),
    ]
