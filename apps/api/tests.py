from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework.authtoken.models import Token

from apps.accounts.constants import (ROLE_ADMIN, ROLE_DRIVER, ROLE_OPERATOR,
                                    ROLE_SUPPLY, ROLE_TRANSPORT,
                                    ROLE_VIEWER, ROLE_WAREHOUSE)
from apps.accounts.models import UserProfile
from apps.api.models import DeviceToken, RequestPhoto
from apps.api.serializers import (BreakdownSerializer, LoginSerializer,
                                 OdometerSerializer, StatusChangeSerializer)
from apps.logistics.constants import (STATUS_DELIVERED, STATUS_PROBLEM,
                                     STATUS_READY_TO_SHIP, STATUS_SHIPPED,
                                     STATUS_WAITING_SUPPLY)
from apps.logistics.models import (Client, LogisticsRequest,
                                  RequestStatusHistory, Warehouse)
from apps.logistics.services import change_request_status
from apps.notifications.models import Notification
from apps.transport.models import Driver, Vehicle


def create_user(username, role_code, mobile_access=True, **flags):
    user = get_user_model().objects.create_user(username=username, password="password", **flags)
    UserProfile.objects.update_or_create(
        user=user,
        defaults={"role": role_code, "phone": "", "is_active": True,
                  "mobile_access_enabled": mobile_access},
    )
    return user


def token_for(user):
    t, _ = Token.objects.get_or_create(user=user)
    return t.key


def auth(client, user):
    client.defaults["HTTP_AUTHORIZATION"] = f"Token {token_for(user)}"


class AppVersionViewTests(TestCase):
    def test_public_access_returns_versions(self):
        response = self.client.get(reverse("api:app_version"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("observer", data)
        self.assertIn("driver", data)


class PermissionsTests(TestCase):
    def setUp(self):
        self.viewer = create_user("perm_viewer", ROLE_VIEWER)
        self.driver = create_user("perm_driver", ROLE_DRIVER)
        self.operator = create_user("perm_operator", ROLE_OPERATOR, mobile_access=False)
        self.superuser = get_user_model().objects.create_superuser(username="perm_admin", password="password")

    def test_viewer_gets_access_to_viewer_endpoints(self):
        auth(self.client, self.viewer)
        response = self.client.get(reverse("api:request_list"))
        self.assertEqual(response.status_code, 200)

    def test_operator_without_mobile_access_gets_forbidden(self):
        auth(self.client, self.operator)
        response = self.client.get(reverse("api:request_list"))
        self.assertEqual(response.status_code, 403)

    def test_driver_gets_access_to_driver_endpoints(self):
        auth(self.client, self.driver)
        response = self.client.get(reverse("api:driver_trip_list"))
        self.assertEqual(response.status_code, 200)

    def test_driver_blocked_from_viewer_endpoints(self):
        auth(self.client, self.driver)
        response = self.client.get(reverse("api:request_list"))
        self.assertEqual(response.status_code, 403)

    def test_superuser_has_full_access(self):
        auth(self.client, self.superuser)
        response = self.client.get(reverse("api:request_list"))
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_blocked(self):
        response = self.client.get(reverse("api:request_list"))
        self.assertEqual(response.status_code, 401)


class LoginViewTests(TestCase):
    def setUp(self):
        self.user = create_user("api_user", ROLE_VIEWER)

    def test_login_returns_token_and_profile(self):
        response = self.client.post(reverse("api:login"), {
            "username": "api_user", "password": "password",
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("token", data)
        self.assertIn("user", data)
        self.assertEqual(data["user"]["username"], "api_user")

    def test_login_invalid_credentials(self):
        response = self.client.post(reverse("api:login"), {
            "username": "api_user", "password": "wrong",
        })
        self.assertEqual(response.status_code, 400)

    def test_login_inactive_user(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post(reverse("api:login"), {
            "username": "api_user", "password": "password",
        })
        self.assertEqual(response.status_code, 400)

    def test_login_no_mobile_access(self):
        no_access = create_user("no_mobile", ROLE_VIEWER, mobile_access=False)
        response = self.client.post(reverse("api:login"), {
            "username": "no_mobile", "password": "password",
        })
        self.assertEqual(response.status_code, 400)


class LoginSerializerTests(TestCase):
    def test_missing_fields(self):
        serializer = LoginSerializer(data={})
        self.assertFalse(serializer.is_valid())


class LogoutViewTests(TestCase):
    def setUp(self):
        self.user = create_user("logout_user", ROLE_VIEWER)

    def test_logout_deletes_token(self):
        auth(self.client, self.user)
        response = self.client.post(reverse("api:logout"))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Token.objects.filter(user=self.user).exists())


class MeViewTests(TestCase):
    def setUp(self):
        self.user = create_user("me_user", ROLE_VIEWER)

    def test_me_returns_profile(self):
        auth(self.client, self.user)
        response = self.client.get(reverse("api:me"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "me_user")


class DeviceTokenTests(TestCase):
    def setUp(self):
        self.user = create_user("device_user", ROLE_VIEWER)

    def test_register_new_token(self):
        auth(self.client, self.user)
        response = self.client.post(reverse("api:device_register"), {
            "fcm_token": "fcm-test-token-001", "platform": "android",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(DeviceToken.objects.filter(user=self.user, fcm_token="fcm-test-token-001").exists())

    def test_reassign_token_from_other_user(self):
        other = create_user("device_other", ROLE_VIEWER)
        DeviceToken.objects.create(user=other, fcm_token="fcm-shared-token", platform="android")

        auth(self.client, self.user)
        response = self.client.post(reverse("api:device_register"), {
            "fcm_token": "fcm-shared-token", "platform": "android",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(DeviceToken.objects.filter(user=other).exists())
        self.assertTrue(DeviceToken.objects.filter(user=self.user, fcm_token="fcm-shared-token").exists())

    def test_unregister_existing_token(self):
        DeviceToken.objects.create(user=self.user, fcm_token="fcm-delete-me", platform="android")
        auth(self.client, self.user)
        response = self.client.delete(reverse("api:device_unregister", kwargs={"fcm_token": "fcm-delete-me"}))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(DeviceToken.objects.filter(fcm_token="fcm-delete-me").exists())

    def test_unregister_nonexistent_token(self):
        auth(self.client, self.user)
        response = self.client.delete(reverse("api:device_unregister", kwargs={"fcm_token": "fcm-gone"}))
        self.assertEqual(response.status_code, 404)


class RequestListViewTests(TestCase):
    def setUp(self):
        self.viewer = create_user("rl_viewer", ROLE_VIEWER)
        self.warehouse = Warehouse.objects.create(name="WH", region="MSK", address="addr")
        self.request = LogisticsRequest.objects.create(
            client_name="Client", client_address="addr", client_contact="C",
            region="MSK", warehouse=self.warehouse, cargo_description="c",
            cargo_places_count=1, cargo_weight_kg=10, cargo_volume_m3=0.1,
            dimensions_text="1", planned_ship_date="2025-01-01",
            planned_delivery_date="2025-01-01", created_by=self.viewer,
        )
        self.request.viewer_users.add(self.viewer)

    def test_list_returns_results(self):
        auth(self.client, self.viewer)
        response = self.client.get(reverse("api:request_list"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("results", data)
        self.assertIn("server_time", data)
        self.assertGreaterEqual(len(data["results"]), 1)

    def test_list_empty_for_non_viewer_request(self):
        other_viewer = create_user("rl_other_viewer", ROLE_VIEWER)
        auth(self.client, other_viewer)
        response = self.client.get(reverse("api:request_list"))
        data = response.json()
        self.assertEqual(len(data["results"]), 0)


class RequestDetailViewTests(TestCase):
    def setUp(self):
        self.viewer = create_user("rd_viewer", ROLE_VIEWER)
        self.warehouse = Warehouse.objects.create(name="WH", region="MSK", address="addr")
        self.request = LogisticsRequest.objects.create(
            client_name="Client", client_address="addr", client_contact="C",
            region="MSK", warehouse=self.warehouse, cargo_description="c",
            cargo_places_count=1, cargo_weight_kg=10, cargo_volume_m3=0.1,
            dimensions_text="1", planned_ship_date="2025-01-01",
            planned_delivery_date="2025-01-01", created_by=self.viewer,
        )
        self.request.viewer_users.add(self.viewer)

    def test_detail_returns_request_data(self):
        auth(self.client, self.viewer)
        response = self.client.get(reverse("api:request_detail", kwargs={"pk": self.request.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], self.request.pk)

    def test_detail_404_for_non_viewer_request(self):
        other_viewer = create_user("rd_other", ROLE_VIEWER)
        auth(self.client, other_viewer)
        response = self.client.get(reverse("api:request_detail", kwargs={"pk": self.request.pk}))
        self.assertEqual(response.status_code, 404)


class NotificationApiViewTests(TestCase):
    def setUp(self):
        self.viewer = create_user("na_viewer", ROLE_VIEWER)

    def test_list_personal_notifications(self):
        Notification.objects.create(recipient_user=self.viewer, message="Hello")
        auth(self.client, self.viewer)
        response = self.client.get(reverse("api:notification_list"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(len(data["results"]), 1)

    def test_mark_read(self):
        notif = Notification.objects.create(recipient_user=self.viewer, is_read=False, message="Read me")
        auth(self.client, self.viewer)
        response = self.client.post(reverse("api:notification_read", kwargs={"pk": notif.pk}))
        self.assertEqual(response.status_code, 200)
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)


class DriverTripListTests(TestCase):
    def setUp(self):
        self.driver = create_user("drv_list2", ROLE_DRIVER)
        self.driver_profile, _ = Driver.objects.get_or_create(
            user=self.driver, defaults={"full_name": "Test Driver", "phone": "+7 900 1"}
        )
        self.warehouse = Warehouse.objects.create(name="WH", region="MSK", address="addr")
        self.vehicle = Vehicle.objects.create(
            name="GAZel", plate_number="А001АА777", max_weight_kg=1500, max_volume_m3=10
        )
        self.request = LogisticsRequest.objects.create(
            client_name="Client", client_address="addr", client_contact="C",
            region="MSK", warehouse=self.warehouse, cargo_description="c",
            cargo_places_count=1, cargo_weight_kg=10, cargo_volume_m3=0.1,
            dimensions_text="1", planned_ship_date="2025-01-01",
            planned_delivery_date="2025-01-01", created_by=self.driver,
            assigned_vehicle=self.vehicle, assigned_driver=self.driver_profile,
            status=STATUS_READY_TO_SHIP,
        )

    def test_driver_sees_own_trip(self):
        auth(self.client, self.driver)
        response = self.client.get(reverse("api:driver_trip_list"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["id"], self.request.pk)


class DriverTripDetailTests(TestCase):
    def setUp(self):
        self.driver = create_user("drv_detail", ROLE_DRIVER)
        self.driver_profile, _ = Driver.objects.update_or_create(
            user=self.driver, defaults={"full_name": "Detail Driver", "phone": "+7 900 1"}
        )
        self.warehouse = Warehouse.objects.create(name="WH", region="MSK", address="addr")
        self.vehicle = Vehicle.objects.create(
            name="GAZel", plate_number="А002АА777", max_weight_kg=1500, max_volume_m3=10
        )
        self.request = LogisticsRequest.objects.create(
            client_name="Client", client_address="addr", client_contact="C",
            region="MSK", warehouse=self.warehouse, cargo_description="c",
            cargo_places_count=1, cargo_weight_kg=10, cargo_volume_m3=0.1,
            dimensions_text="1", planned_ship_date="2025-01-01",
            planned_delivery_date="2025-01-01", created_by=self.driver,
            assigned_vehicle=self.vehicle, assigned_driver=self.driver_profile,
        )

    def test_detail_returns_trip_data(self):
        auth(self.client, self.driver)
        response = self.client.get(reverse("api:driver_trip_detail", kwargs={"pk": self.request.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], self.request.pk)


class DriverTripStatusTests(TestCase):
    def setUp(self):
        self.driver = create_user("drv_status", ROLE_DRIVER)
        self.driver_profile, _ = Driver.objects.update_or_create(
            user=self.driver, defaults={"full_name": "Status Driver", "phone": "+7 900 1"}
        )
        self.warehouse = Warehouse.objects.create(name="WH", region="MSK", address="addr")
        self.vehicle = Vehicle.objects.create(
            name="GAZel", plate_number="А003АА777", max_weight_kg=1500, max_volume_m3=10
        )
        self.request = LogisticsRequest.objects.create(
            client_name="Client", client_address="addr", client_contact="C",
            region="MSK", warehouse=self.warehouse, cargo_description="c",
            cargo_places_count=1, cargo_weight_kg=10, cargo_volume_m3=0.1,
            dimensions_text="1", planned_ship_date="2025-01-01",
            planned_delivery_date="2025-01-01", created_by=self.driver,
            assigned_vehicle=self.vehicle, assigned_driver=self.driver_profile,
            status=STATUS_READY_TO_SHIP,
        )

    def test_allowed_status_transition(self):
        auth(self.client, self.driver)
        response = self.client.post(
            reverse("api:driver_trip_status", kwargs={"pk": self.request.pk}),
            {"status": STATUS_SHIPPED},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, STATUS_SHIPPED)

    def test_disallowed_status_transition(self):
        auth(self.client, self.driver)
        response = self.client.post(
            reverse("api:driver_trip_status", kwargs={"pk": self.request.pk}),
            {"status": STATUS_DELIVERED},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)


class DriverTripOdometerTests(TestCase):
    def setUp(self):
        self.driver = create_user("drv_odo", ROLE_DRIVER)
        self.driver_profile, _ = Driver.objects.update_or_create(
            user=self.driver, defaults={"full_name": "Odo Driver", "phone": "+7 900 1"}
        )
        self.warehouse = Warehouse.objects.create(name="WH", region="MSK", address="addr")
        self.vehicle = Vehicle.objects.create(
            name="GAZel", plate_number="А004АА777", max_weight_kg=1500, max_volume_m3=10, odometer_km=10000
        )
        self.request = LogisticsRequest.objects.create(
            client_name="Client", client_address="addr", client_contact="C",
            region="MSK", warehouse=self.warehouse, cargo_description="c",
            cargo_places_count=1, cargo_weight_kg=10, cargo_volume_m3=0.1,
            dimensions_text="1", planned_ship_date="2025-01-01",
            planned_delivery_date="2025-01-01", created_by=self.driver,
            assigned_vehicle=self.vehicle, assigned_driver=self.driver_profile,
        )

    def test_odometer_records_history_and_updates_vehicle(self):
        auth(self.client, self.driver)
        response = self.client.post(
            reverse("api:driver_trip_odometer", kwargs={"pk": self.request.pk}),
            {"odometer_km": 15000},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            RequestStatusHistory.objects.filter(
                request=self.request, comment="odometer:15000"
            ).exists()
        )
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.odometer_km, 15000)

    def test_odometer_does_not_downgrade_vehicle(self):
        self.vehicle.odometer_km = 50000
        self.vehicle.save()
        auth(self.client, self.driver)
        response = self.client.post(
            reverse("api:driver_trip_odometer", kwargs={"pk": self.request.pk}),
            {"odometer_km": 30000},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.odometer_km, 50000)


class DriverTripPhotosTests(TestCase):
    def setUp(self):
        self.driver = create_user("drv_photos", ROLE_DRIVER)
        self.driver_profile, _ = Driver.objects.update_or_create(
            user=self.driver, defaults={"full_name": "Photo Driver", "phone": "+7 900 1"}
        )
        self.warehouse = Warehouse.objects.create(name="WH", region="MSK", address="addr")
        self.vehicle = Vehicle.objects.create(
            name="GAZel", plate_number="А005АА777", max_weight_kg=1500, max_volume_m3=10
        )
        self.request = LogisticsRequest.objects.create(
            client_name="Client", client_address="addr", client_contact="C",
            region="MSK", warehouse=self.warehouse, cargo_description="c",
            cargo_places_count=1, cargo_weight_kg=10, cargo_volume_m3=0.1,
            dimensions_text="1", planned_ship_date="2025-01-01",
            planned_delivery_date="2025-01-01", created_by=self.driver,
            assigned_vehicle=self.vehicle, assigned_driver=self.driver_profile,
        )

    def test_get_photos_empty_list(self):
        auth(self.client, self.driver)
        response = self.client.get(reverse("api:driver_trip_photos", kwargs={"pk": self.request.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["results"]), 0)

    def test_post_photo_creates_record(self):
        buffer = BytesIO()
        Image.new("RGB", (1, 1), color="white").save(buffer, format="JPEG")
        image_bytes = buffer.getvalue()

        auth(self.client, self.driver)
        response = self.client.post(
            reverse("api:driver_trip_photos", kwargs={"pk": self.request.pk}),
            {"file": SimpleUploadedFile("cargo.jpg", image_bytes, content_type="image/jpeg"),
             "photo_type": "loading"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(RequestPhoto.objects.filter(request=self.request).count(), 1)


class DriverBreakdownTests(TestCase):
    def setUp(self):
        self.driver = create_user("drv_breakdown", ROLE_DRIVER)
        self.driver_profile, _ = Driver.objects.update_or_create(
            user=self.driver, defaults={"full_name": "Break Driver", "phone": "+7 900 1"}
        )
        self.transport_user = create_user("transport_bd", ROLE_TRANSPORT)
        self.warehouse = Warehouse.objects.create(name="WH", region="MSK", address="addr")
        self.vehicle = Vehicle.objects.create(
            name="GAZel", plate_number="А006АА777", max_weight_kg=1500, max_volume_m3=10
        )
        self.request = LogisticsRequest.objects.create(
            client_name="Client", client_address="addr", client_contact="C",
            region="MSK", warehouse=self.warehouse, cargo_description="c",
            cargo_places_count=1, cargo_weight_kg=10, cargo_volume_m3=0.1,
            dimensions_text="1", planned_ship_date="2025-01-01",
            planned_delivery_date="2025-01-01", created_by=self.driver,
            assigned_vehicle=self.vehicle, assigned_driver=self.driver_profile,
        )

    def test_breakdown_creates_problem_and_notifies_transport(self):
        auth(self.client, self.driver)
        response = self.client.post(
            reverse("api:driver_breakdown"),
            {"description": "Двигатель заглох", "request_id": self.request.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, STATUS_PROBLEM)
        self.assertTrue(
            Notification.objects.filter(recipient_role=ROLE_TRANSPORT, message__icontains="Поломка").exists()
        )

    def test_breakdown_without_request_id(self):
        auth(self.client, self.driver)
        response = self.client.post(
            reverse("api:driver_breakdown"),
            {"description": "Двигатель не заводится"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("problem_id", response.json())


class StatusChangeSerializerTests(TestCase):
    def test_valid_status(self):
        s = StatusChangeSerializer(data={"status": STATUS_SHIPPED})
        self.assertTrue(s.is_valid(), s.errors)

    def test_invalid_status(self):
        s = StatusChangeSerializer(data={"status": "flying"})
        self.assertFalse(s.is_valid())


class OdometerSerializerTests(TestCase):
    def test_valid_km(self):
        s = OdometerSerializer(data={"odometer_km": 12345})
        self.assertTrue(s.is_valid(), s.errors)

    def test_negative_km(self):
        s = OdometerSerializer(data={"odometer_km": -1})
        self.assertFalse(s.is_valid())


class BreakdownSerializerTests(TestCase):
    def test_valid_description(self):
        s = BreakdownSerializer(data={"description": "Поломка двигателя"})
        self.assertTrue(s.is_valid(), s.errors)

    def test_too_short_description(self):
        s = BreakdownSerializer(data={"description": "ab"})
        self.assertFalse(s.is_valid())
