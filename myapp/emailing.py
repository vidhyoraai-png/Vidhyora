from django.conf import settings
from django.core.mail import send_mail


def send_store_email(subject, body, to):
    """Sends an app email via the Gmail account hardcoded in settings.py.
    The dashboard's Email Settings page is deactivated — this is the only
    email path. `to` is a list of recipient addresses."""
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, to, fail_silently=False)


def get_notify_email():
    """Where store notifications (new orders, contact leads) should go."""
    return settings.LEAD_RECIPIENT_EMAIL
