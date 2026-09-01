from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0044_remove_personal_name_and_address_knowledge'),
    ]

    operations = [
        migrations.AddField(
            model_name='storeprofile',
            name='manual_amount_paid',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Amount manually recorded as paid when staff creates or edits this customer.',
                max_digits=12,
            ),
        ),
    ]
