from django.db import migrations, models


def backfill_manual_payment_dates(apps, schema_editor):
    StoreProfile = apps.get_model('myapp', 'StoreProfile')
    for profile in StoreProfile.objects.filter(manual_amount_paid__gt=0).select_related('user'):
        profile.manual_payment_received_at = profile.user.date_joined
        profile.save(update_fields=['manual_payment_received_at'])


class Migration(migrations.Migration):
    dependencies = [('myapp', '0056_storeprofile_login_count')]

    operations = [
        migrations.AddField(
            model_name='storeprofile',
            name='manual_payment_received_at',
            field=models.DateTimeField(
                blank=True,
                help_text='Date and time the manually recorded payment was received.',
                null=True,
            ),
        ),
        migrations.RunPython(backfill_manual_payment_dates, migrations.RunPython.noop),
    ]
