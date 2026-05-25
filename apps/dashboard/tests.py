import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.models import UserProfile
from apps.dashboard.models import SiteBranding


class SiteBrandingTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_root)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)

        self.user = get_user_model().objects.create_superuser(username="admin", password="password")
        UserProfile.objects.update_or_create(user=self.user, defaults={"role": ROLE_ADMIN, "is_active": True})

    def test_company_logo_is_available_in_base_menu(self):
        branding = SiteBranding.current()
        branding.company_logo = SimpleUploadedFile("logo.webp", b"logo-content", content_type="image/webp")
        branding.save()
        self.client.force_login(self.user)

        response = self.client.get(reverse("request_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Логотип компании")
        self.assertContains(response, branding.company_logo.url)
