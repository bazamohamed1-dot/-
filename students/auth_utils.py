import secrets
import string
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from .models import SchoolSettings
import logging

logger = logging.getLogger(__name__)

def generate_random_password(length=12):
    """Generates a secure random password."""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    while True:
        password = ''.join(secrets.choice(alphabet) for i in range(length))
        if (any(c.islower() for c in password)
                and any(c.isupper() for c in password)
                and any(c.isdigit() for c in password)):
            return password

def send_new_account_email(user, password):
    """Sends an email to the new user with their temporary password."""
    try:
        settings_obj = SchoolSettings.objects.first()
        school_name = settings_obj.name if settings_obj else "Baza Systems"

        subject = f"Welcome to {school_name} - Your Account Credentials"
        message = f"""
Hello {user.username},

Your account for {school_name} has been created.

Username: {user.username}
Temporary Password: {password}

Please log in at: {settings.APP_DOMAIN}

IMPORTANT: You will be required to change your password upon first login.

Best regards,
Administrator
"""
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send new account email: {e}")
        return False

def send_password_reset_email(user, token):
    """Sends a password reset link."""
    try:
        settings_obj = SchoolSettings.objects.first()
        school_name = settings_obj.name if settings_obj else "Baza Systems"

        link = f"{settings.APP_DOMAIN}/reset-password/{token}/"

        subject = f"Password Reset Request - {school_name}"
        message = f"""
Hello {user.username},

You requested a password reset. Please click the link below to reset your password:

{link}

This link is valid for 15 minutes.

If you did not request this, please ignore this email.

Best regards,
{school_name}
"""
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send reset email: {e}")
        return False
