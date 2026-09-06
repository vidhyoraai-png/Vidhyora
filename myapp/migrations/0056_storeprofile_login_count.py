from django.db import migrations, models


def backfill_known_logins(apps, schema_editor):
    StoreProfile = apps.get_model('myapp', 'StoreProfile')
    # Django only retains the most recent historical login, so older exact
    # counts cannot be reconstructed. Record a truthful minimum of one for
    # accounts known to have logged in before this counter existed.
    StoreProfile.objects.filter(
        login_count=0,
        user__last_login__isnull=False,
    ).update(login_count=1)


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0055_alter_knowledgeentry_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='storeprofile',
            name='login_count',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Number of successful account logins recorded by Vidhyora.',
            ),
        ),
        migrations.RunPython(backfill_known_logins, migrations.RunPython.noop),
    ]
