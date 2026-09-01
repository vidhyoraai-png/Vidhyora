from django.contrib.sessions.models import Session
from django.db import transaction

from .models import ActiveUserSession


def register_active_session(user, session_key):
    """Claim a user's single login slot and remove the previous session."""
    if not user or not user.is_authenticated or not session_key:
        return

    with transaction.atomic():
        active, _created = ActiveUserSession.objects.select_for_update().get_or_create(
            user=user,
            defaults={'session_key': session_key},
        )
        previous_key = active.session_key
        if previous_key != session_key:
            active.session_key = session_key
            active.save(update_fields=['session_key', 'updated_at'])

    if previous_key and previous_key != session_key:
        Session.objects.filter(session_key=previous_key).delete()


def clear_active_session(user, session_key):
    """Release the slot only when the device logging out currently owns it."""
    if user and user.is_authenticated and session_key:
        ActiveUserSession.objects.filter(user=user, session_key=session_key).delete()
