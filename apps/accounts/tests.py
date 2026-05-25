from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from apps.accounts.admin import CustomUserAdmin
from apps.accounts.models import UserProfile


class UserAdminTests(TestCase):
    def test_user_profile_inline_is_hidden_on_add_and_visible_on_change(self):
        User = get_user_model()
        admin_user = User.objects.create_superuser(username="admin", password="password")
        new_user = User.objects.create_user(username="new-user", password="password")
        request = RequestFactory().get("/admin/accounts/user/add/")
        request.user = admin_user
        model_admin = CustomUserAdmin(User, AdminSite())

        self.assertEqual(model_admin.get_inline_instances(request, obj=None), [])
        self.assertEqual(len(model_admin.get_inline_instances(request, obj=new_user)), 1)
        self.assertTrue(UserProfile.objects.filter(user=new_user).exists())
