import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0001_initial"),
        ("tickets", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="timeentry",
            name="invoice_line",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="billing.invoiceline",
            ),
        ),
    ]
