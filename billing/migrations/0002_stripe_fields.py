from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="stripe_payment_link_url",
            field=models.URLField(blank=True, max_length=512),
        ),
        migrations.AlterField(
            model_name="payment",
            name="xero_payment_id",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="payment",
            name="stripe_payment_intent_id",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.UniqueConstraint(
                condition=~Q(xero_payment_id=""),
                fields=("xero_payment_id",),
                name="uniq_payment_xero_id_set",
            ),
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.UniqueConstraint(
                condition=~Q(stripe_payment_intent_id=""),
                fields=("stripe_payment_intent_id",),
                name="uniq_payment_stripe_pi_set",
            ),
        ),
    ]
