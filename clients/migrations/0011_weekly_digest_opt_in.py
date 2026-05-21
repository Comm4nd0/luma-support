from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0010_client_stripe_customer_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="weekly_digest_opt_in",
            field=models.BooleanField(default=True),
        ),
    ]
