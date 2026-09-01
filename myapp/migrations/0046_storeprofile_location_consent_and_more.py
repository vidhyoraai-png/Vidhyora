from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0045_storeprofile_manual_amount_paid'),
    ]

    operations = [
        migrations.AddField(
            model_name='storeprofile',
            name='location_accuracy_m',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='storeprofile',
            name='location_consent',
            field=models.CharField(
                choices=[('unknown', 'Not asked'), ('granted', 'Enabled'), ('denied', 'Declined')],
                default='unknown',
                help_text='Whether the user allowed a one-time browser location request.',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='storeprofile',
            name='location_latitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name='storeprofile',
            name='location_longitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name='storeprofile',
            name='location_updated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
