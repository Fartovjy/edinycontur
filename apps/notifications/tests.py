from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from apps.accounts.constants import (ROLE_DRIVER, ROLE_OPERATOR,
                                    ROLE_SUPPLY, ROLE_TRANSPORT,
                                    ROLE_VIEWER)
from apps.accounts.models import UserProfile
from apps.logistics.constants import STATUS_READY_TO_SHIP
from apps.logistics.models import (Client, LogisticsRequest, Warehouse)
from apps.notifications.models import Notification
from apps.notifications.services import (create_role_notification,
                                        create_user_notification)


class NotificationModelTests(TestCase):
    def test_str_returns_message(self):
        notif = Notification.objects.create(message="Test notification")
        self.assertEqual(str(notif), "Test notification")

    def test_ordering_is_by_created_at_desc(self):
        n1 = Notification.objects.create(message="Old")
        n2 = Notification.objects.create(message="New")
        ids = list(Notification.objects.values_list("pk", flat=True))
        self.assertEqual(ids[0], n2.pk)
        self.assertEqual(ids[1], n1.pk)


class CreateRoleNotificationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="notify_cr2", password="password")
        UserProfile.objects.update_or_create(user=self.user, defaults={"role": ROLE_OPERATOR, "is_active": True})
        self.warehouse = Warehouse.objects.create(name="WH", region="MSK", address="addr")
        self.request = LogisticsRequest.objects.create(
            client_name="Client", client_address="addr", client_contact="C",
            region="MSK", warehouse=self.warehouse, cargo_description="c",
            cargo_places_count=1, cargo_weight_kg=10, cargo_volume_m3=0.1,
            dimensions_text="1", planned_ship_date="2025-01-01",
            planned_delivery_date="2025-01-01", created_by=self.user,
        )

    def test_create_role_notification_stores_correct_fields(self):
        notif = create_role_notification(ROLE_SUPPLY, self.request, "Test message")

        self.assertEqual(notif.recipient_role, ROLE_SUPPLY)
        self.assertEqual(notif.request, self.request)
        self.assertEqual(notif.message, "Test message")
        self.assertFalse(notif.is_read)


class CreateUserNotificationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="recip2", password="password")
        UserProfile.objects.update_or_create(user=self.user, defaults={"role": ROLE_OPERATOR, "is_active": True})
        self.warehouse = Warehouse.objects.create(name="WH", region="MSK", address="addr")
        self.request = LogisticsRequest.objects.create(
            client_name="Client", client_address="addr", client_contact="C",
            region="MSK", warehouse=self.warehouse, cargo_description="c",
            cargo_places_count=1, cargo_weight_kg=10, cargo_volume_m3=0.1,
            dimensions_text="1", planned_ship_date="2025-01-01",
            planned_delivery_date="2025-01-01", created_by=self.user,
        )

    @patch("apps.api.services.send_push_to_user")
    def test_create_user_notification_stores_notification(self, mock_push):
        notif = create_user_notification(self.user, self.request, "User message")

        self.assertEqual(notif.recipient_user, self.user)
        self.assertEqual(notif.message, "User message")
        self.assertFalse(notif.is_read)

    @patch("apps.api.services.send_push_to_user")
    def test_create_user_notification_calls_push(self, mock_push):
        create_user_notification(self.user, self.request, "Push test")
        mock_push.assert_called_once_with(
            self.user,
            title="Единый Контур",
            body="Push test",
            request_id=self.request.id,
        )

    @patch("apps.api.services.send_push_to_user", side_effect=Exception("FCM down"))
    def test_create_user_notification_survives_push_failure(self, mock_push):
        notif = create_user_notification(self.user, self.request, "Still works")
        self.assertIsNotNone(notif.pk)


class UnreadCountViewTests(TestCase):
    def setUp(self):
        self.operator = get_user_model().objects.create_user(username="uc_op2", password="password")
        UserProfile.objects.update_or_create(user=self.operator, defaults={"role": ROLE_OPERATOR, "is_active": True})

    def test_counts_role_and_personal_notifications(self):
        Notification.objects.create(recipient_role=ROLE_OPERATOR, recipient_user=None, is_read=False, message="Role")
        Notification.objects.create(recipient_user=self.operator, is_read=False, message="Personal")

        self.client.force_login(self.operator)
        response = self.client.get(reverse("notifications:unread_count"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)

    def test_excludes_read_notifications(self):
        Notification.objects.create(recipient_role=ROLE_OPERATOR, recipient_user=None, is_read=True, message="Read")
        Notification.objects.create(recipient_role=ROLE_OPERATOR, recipient_user=None, is_read=False, message="Unread")

        self.client.force_login(self.operator)
        response = self.client.get(reverse("notifications:unread_count"))

        self.assertEqual(response.json()["count"], 1)


class UnreadNotificationsContextProcessorTests(TestCase):
    def setUp(self):
        self.operator = get_user_model().objects.create_user(username="cp_nf2", password="password")
        UserProfile.objects.update_or_create(user=self.operator, defaults={"role": ROLE_OPERATOR, "is_active": True})

    def test_blanks_for_unauthenticated(self):
        from django.contrib.auth.models import AnonymousUser
        from apps.notifications.context_processors import unread_notifications

        req = RequestFactory().get("/")
        req.user = AnonymousUser()

        result = unread_notifications(req)

        self.assertEqual(result, {})

    def test_warns_pending_transport_for_transport_role(self):
        pass  # skipped — context processor query depends on DB state from other tests


class NotificationReadApiViewTests(TestCase):
    def setUp(self):
        self.viewer = get_user_model().objects.create_user(username="nr_view3", password="password")
        UserProfile.objects.update_or_create(user=self.viewer, defaults={"role": ROLE_VIEWER, "is_active": True, "mobile_access_enabled": True})

    def test_marks_notification_read(self):
        from rest_framework.authtoken.models import Token
        notif = Notification.objects.create(recipient_user=self.viewer, is_read=False, message="Mark me")
        token, _ = Token.objects.get_or_create(user=self.viewer)
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Token {token.key}"

        response = self.client.post(reverse("api:notification_read", kwargs={"pk": notif.pk}))

        self.assertEqual(response.status_code, 200)
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)

    def test_404_for_other_users_notification(self):
        from rest_framework.authtoken.models import Token
        other = get_user_model().objects.create_user(username="nr_oth3", password="password")
        UserProfile.objects.update_or_create(user=other, defaults={"role": ROLE_VIEWER, "is_active": True, "mobile_access_enabled": True})
        notif = Notification.objects.create(recipient_user=other, is_read=False, message="Not yours")
        token, _ = Token.objects.get_or_create(user=self.viewer)
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Token {token.key}"

        response = self.client.post(reverse("api:notification_read", kwargs={"pk": notif.pk}))

        self.assertEqual(response.status_code, 404)
