"""
Signals for the accounts app to handle automatic device creation for 2FA.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice
from .models import CustomUser


@receiver(post_save, sender=CustomUser)
def create_otp_device(sender, instance, created, **kwargs):
    """
    Automatically create a TOTPDevice for new users.

    Args:
        sender: The model class that triggered the signal.
        instance: The instance of the model that was saved.
        created: Boolean indicating whether the instance was created.
        **kwargs: Additional keyword arguments.
    """
    if created:
        # Create a TOTP device for the user
        TOTPDevice.objects.create(
            user=instance,
            name="default",
            confirmed=True
        )
