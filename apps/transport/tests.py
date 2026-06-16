from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.transport.models import Driver, Vehicle


class VehicleComputedPropertiesTests(TestCase):
    def test_service_remaining_km_returns_none_when_service_due_km_is_absent(self):
        vehicle = Vehicle.objects.create(plate_number="А001АА777", odometer_km=50000)

        self.assertIsNone(vehicle.service_remaining_km)

    def test_service_remaining_km_returns_difference(self):
        vehicle = Vehicle.objects.create(plate_number="А002АА777", odometer_km=20000, service_due_km=35000)

        self.assertEqual(vehicle.service_remaining_km, 15000)

    def test_service_remaining_km_floors_to_zero_when_overdue(self):
        vehicle = Vehicle.objects.create(plate_number="А003АА777", odometer_km=60000, service_due_km=50000)

        self.assertEqual(vehicle.service_remaining_km, 0)

    def test_service_remaining_km_handles_none_odometer(self):
        vehicle = Vehicle.objects.create(plate_number="А004АА777", odometer_km=None, service_due_km=15000)

        self.assertEqual(vehicle.service_remaining_km, 15000)

    def test_inspection_days_left_returns_none_when_no_date(self):
        vehicle = Vehicle.objects.create(plate_number="А005АА777")

        self.assertIsNone(vehicle.inspection_days_left)

    def test_inspection_days_left_positive_future(self):
        vehicle = Vehicle.objects.create(
            plate_number="А006АА777",
            next_inspection_date=timezone.localdate() + timedelta(days=10),
        )

        self.assertEqual(vehicle.inspection_days_left, 10)

    def test_inspection_days_left_negative_past(self):
        vehicle = Vehicle.objects.create(
            plate_number="А007АА777",
            next_inspection_date=timezone.localdate() - timedelta(days=5),
        )

        self.assertEqual(vehicle.inspection_days_left, -5)

    def test_inspection_days_left_zero_today(self):
        vehicle = Vehicle.objects.create(
            plate_number="А008АА777",
            next_inspection_date=timezone.localdate(),
        )

        self.assertEqual(vehicle.inspection_days_left, 0)

    def test_inspection_warning_within_threshold(self):
        vehicle = Vehicle.objects.create(
            plate_number="А009АА777",
            next_inspection_date=timezone.localdate() + timedelta(days=21),
        )

        self.assertTrue(vehicle.inspection_warning)

    def test_inspection_warning_false_outside_threshold(self):
        vehicle = Vehicle.objects.create(
            plate_number="А010АА777",
            next_inspection_date=timezone.localdate() + timedelta(days=22),
        )

        self.assertFalse(vehicle.inspection_warning)

    def test_inspection_warning_true_when_overdue(self):
        vehicle = Vehicle.objects.create(
            plate_number="А011АА777",
            next_inspection_date=timezone.localdate() - timedelta(days=1),
        )

        self.assertTrue(vehicle.inspection_warning)

    def test_inspection_overdue_true(self):
        vehicle = Vehicle.objects.create(
            plate_number="А012АА777",
            next_inspection_date=timezone.localdate() - timedelta(days=1),
        )

        self.assertTrue(vehicle.inspection_overdue)

    def test_inspection_overdue_false_future(self):
        vehicle = Vehicle.objects.create(
            plate_number="А013АА777",
            next_inspection_date=timezone.localdate() + timedelta(days=10),
        )

        self.assertFalse(vehicle.inspection_overdue)


class DriverChatIdTests(TestCase):
    def test_chat_id_returns_telegram_chat_id_when_set(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(username="driver1", password="password")
        driver = Driver.objects.create(
            user=user,
            full_name="Иван Водитель",
            phone="+7 900 1",
            telegram_chat_id="123456789",
        )

        self.assertEqual(driver.chat_id, "123456789")

    def test_chat_id_falls_back_to_profile_telegram_id(self):
        from django.contrib.auth import get_user_model

        from apps.accounts.models import UserProfile

        user = get_user_model().objects.create_user(username="driver_t2", password="password")
        UserProfile.objects.update_or_create(
            user=user,
            defaults={"role": "driver", "telegram_id": "profile-chat-id", "is_active": True},
        )
        driver, _ = Driver.objects.get_or_create(
            user=user,
            defaults={"full_name": "Петр Водитель", "phone": "+7 900 2", "telegram_chat_id": ""},
        )

        self.assertEqual(driver.chat_id, "profile-chat-id")

    def test_chat_id_returns_empty_when_none_set(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(username="driver3", password="password")
        driver = Driver.objects.create(
            user=user,
            full_name="Сергей Водитель",
            phone="+7 900 3",
        )

        self.assertEqual(driver.chat_id, "")
