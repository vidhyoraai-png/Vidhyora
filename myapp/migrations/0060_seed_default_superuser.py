from django.db import migrations

# Guarantees a permanent superuser account exists on any database this
# project runs against (fresh installs, restored backups, etc.) so there is
# always at least one way into Django admin / the dashboard without a manual
# createsuperuser step. Idempotent: safe to run against a database that
# already has this account (e.g. a restored backup), and never touches an
# existing account's password if one is already there.
DEFAULT_SUPERUSER_EMAIL = 'rnt@gmail.com'
DEFAULT_SUPERUSER_PASSWORD = 'rnt54321'


def create_default_superuser(apps, schema_editor):
    # auth.User is stable, unmodified-by-this-project's-migrations, and
    # set_password()/check_password() only exist on the real model class —
    # the historical model from apps.get_model() would lose them.
    from django.contrib.auth.models import User

    user, created = User.objects.get_or_create(
        username=DEFAULT_SUPERUSER_EMAIL,
        defaults={
            'email': DEFAULT_SUPERUSER_EMAIL,
            'is_staff': True,
            'is_superuser': True,
        },
    )
    if created:
        user.set_password(DEFAULT_SUPERUSER_PASSWORD)
        user.save(update_fields=['password'])
    elif not (user.is_staff and user.is_superuser):
        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=['is_staff', 'is_superuser'])


class Migration(migrations.Migration):
    dependencies = [('myapp', '0059_remove_legacy_store')]
    operations = [migrations.RunPython(create_default_superuser, migrations.RunPython.noop)]
