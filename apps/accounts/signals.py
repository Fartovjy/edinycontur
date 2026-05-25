from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .constants import ROLE_DRIVER, ROLE_OPERATOR
from .models import UserProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(
            user=instance,
            defaults={
                "role": ROLE_OPERATOR,
                "telegram_id": "",
                "is_active": instance.is_active,
            },
        )


@receiver(post_save, sender=UserProfile)
def create_driver_for_driver_profile(sender, instance, **kwargs):
    if instance.role != ROLE_DRIVER:
        return

    from apps.transport.models import Driver

    full_name = instance.user.get_full_name() or instance.user.username
    Driver.objects.get_or_create(
        user=instance.user,
        defaults={
            "full_name": full_name,
            "phone": instance.phone,
            "telegram_chat_id": instance.telegram_id,
            "is_active": instance.is_active,
        },
    )
