"""Clears manual_amount_paid on any profile above the ₹499 ceiling.

The Add-user and Edit-signup forms now cap this field at ₹499, but rows
entered before that cap existed can still carry a bad, higher value. Run
this any time (safe to re-run) to wipe those back to 0 so the Signups total
stops including them and staff are prompted to re-enter a valid amount the
next time they edit that signup.
"""
from myapp.forms import MAX_AMOUNT_PAID
from myapp.models import StoreProfile
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = f'Clear manual_amount_paid on any profile recorded above the ₹{MAX_AMOUNT_PAID} ceiling.'

    def handle(self, *args, **options):
        over_limit = StoreProfile.objects.filter(manual_amount_paid__gt=MAX_AMOUNT_PAID)
        count = over_limit.count()
        if not count:
            self.stdout.write(self.style.SUCCESS('No profiles above the ceiling — nothing to do.'))
            return
        for profile in over_limit:
            email = profile.user.email if profile.user_id else '(no user)'
            self.stdout.write(f'  {email}: {profile.manual_amount_paid} -> 0')
            profile.manual_amount_paid = 0
            profile.save(update_fields=['manual_amount_paid'])
        self.stdout.write(self.style.SUCCESS(f'Cleared manual_amount_paid on {count} profile(s).'))
