from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.accounts.constants import ROLE_VIEWER
from apps.accounts.models import UserProfile


class Command(BaseCommand):
    help = "Creates a viewer user (username=viewer, password=password)"

    def handle(self, *args, **options):
        User = get_user_model()
        user, created = User.objects.get_or_create(
            username="viewer",
            defaults={"first_name": "Наблюдатель", "last_name": ""},
        )
        if created:
            user.set_password("password")
            user.save()
            self.stdout.write(self.style.SUCCESS("Viewer user created: username=viewer, password=password"))
        else:
            self.stdout.write("Viewer user already exists.")

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = ROLE_VIEWER
        profile.save(update_fields=["role"])
        self.stdout.write(f"Profile role set to '{ROLE_VIEWER}'.")
