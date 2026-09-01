from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from .single_device import clear_active_session, register_active_session


@receiver(user_logged_in)
def claim_single_device_login(sender, request, user, **kwargs):
    if request is None:
        return
    if not request.session.session_key:
        request.session.save()
    register_active_session(user, request.session.session_key)


@receiver(user_logged_out)
def release_single_device_login(sender, request, user, **kwargs):
    if request is None or user is None:
        return
    clear_active_session(user, request.session.session_key)
