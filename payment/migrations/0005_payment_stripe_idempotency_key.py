import uuid

from django.db import migrations, models


def populate_idempotency_keys(apps, schema_editor):
    Payment = apps.get_model("payment", "Payment")
    database = schema_editor.connection.alias

    for payment in Payment.objects.using(database).filter(
        stripe_idempotency_key__isnull=True,
    ).iterator():
        payment.stripe_idempotency_key = uuid.uuid4()
        payment.save(
            using=database,
            update_fields=["stripe_idempotency_key"],
        )


class Migration(migrations.Migration):

    dependencies = [
        ("payment", "0004_payment_stripe_checkout_session_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="stripe_idempotency_key",
            field=models.UUIDField(
                editable=False,
                null=True,
            ),
        ),
        migrations.RunPython(
            populate_idempotency_keys,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="payment",
            name="stripe_idempotency_key",
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                unique=True,
            ),
        ),
    ]
