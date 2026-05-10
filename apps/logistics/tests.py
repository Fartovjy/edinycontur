import shutil
import tempfile
import zipfile
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib import admin as django_admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.constants import (
    ROLE_ADMIN,
    ROLE_DRIVER,
    ROLE_MANAGER,
    ROLE_OPERATOR,
    ROLE_SUPPLY,
    ROLE_TRANSPORT,
    ROLE_WAREHOUSE,
)
from apps.accounts.models import Role, UserProfile
from apps.documents.forms import AttachmentForm
from apps.documents.models import Attachment
from apps.logistics.admin import LogisticsRequestAdmin
from apps.logistics.archivist import archive_due_requests, archive_requests_for_date
from apps.logistics.constants import (
    STATUS_CLOSED,
    STATUS_CREATED,
    STATUS_DELIVERED,
    STATUS_IN_WAREHOUSE,
    STATUS_IN_TRANSIT,
    STATUS_PROBLEM,
    STATUS_READY_TO_SHIP,
    STATUS_WAITING_ARRIVAL,
    STATUS_WAITING_SUPPLY,
)
from apps.logistics.models import Client, LogisticsRequest, RequestStatusHistory, Warehouse
from apps.logistics.services import change_request_status
from apps.notifications.models import Notification
from apps.problems.models import ProblemReport
from apps.transport.models import Driver, Vehicle


class LogisticsMvpTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.archive_root = Path(self.media_root) / "archives"
        self.archive_work_root = Path(self.media_root) / "archive_work"
        self.settings_override = override_settings(
            MEDIA_ROOT=self.media_root,
            ARCHIVE_ROOT=self.archive_root,
            ARCHIVE_WORK_ROOT=self.archive_work_root,
            MAX_UPLOAD_SIZE_MB=1,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)

        self.user = get_user_model().objects.create_user(username="operator", password="password")
        self.responsible = get_user_model().objects.create_user(username="manager", password="password")
        self.client_record = Client.objects.create(
            name="Тестовый клиент",
            region="Москва",
            contact_name="Иван Иванов",
            phone="+7 900 000-00-00",
        )
        self.warehouse = Warehouse.objects.create(
            name="Тестовый склад",
            region="Москва",
            address="Москва, тестовый адрес",
        )

    def _create_request(self, **overrides):
        defaults = {
            "client_name": "Тестовый клиент",
            "client_address": "Москва, ул. Тестовая, 1",
            "client_contact": "Иван Иванов, +7 900 000-00-00",
            "region": "Москва",
            "warehouse": self.warehouse,
            "cargo_description": "Тестовый груз",
            "cargo_places_count": 3,
            "cargo_weight_kg": Decimal("120.50"),
            "cargo_volume_m3": Decimal("1.250"),
            "dimensions_text": "3 коробки 60x40x40",
            "planned_ship_date": timezone.localdate(),
            "planned_delivery_date": timezone.localdate(),
            "created_by": self.user,
        }
        defaults.update(overrides)
        return LogisticsRequest.objects.create(**defaults)

    def test_logistics_request_can_be_created(self):
        request = self._create_request(priority=LogisticsRequest.PRIORITY_VIP, cz_required=True, cz_problem=True)

        self.assertEqual(request.client_name, "Тестовый клиент")
        self.assertEqual(request.status, STATUS_CREATED)
        self.assertEqual(request.priority, LogisticsRequest.PRIORITY_VIP)
        self.assertTrue(request.cz_required)
        self.assertTrue(request.cz_problem)

    def test_request_number_is_generated_once_and_incremented(self):
        first = self._create_request()
        second = self._create_request(client_name="Второй клиент")
        original_number = first.request_number

        first.client_name = "Обновленный клиент"
        first.save()
        first.refresh_from_db()

        prefix = timezone.localdate().strftime("%d%m%y - ")
        self.assertEqual(first.request_number, f"{prefix}01")
        self.assertEqual(second.request_number, f"{prefix}02")
        self.assertEqual(first.request_number, original_number)

    def test_change_request_status_creates_history_record(self):
        request = self._create_request()

        history = change_request_status(request, STATUS_WAITING_SUPPLY, self.user, "Передано снабжению")
        request.refresh_from_db()

        self.assertEqual(request.status, STATUS_WAITING_SUPPLY)
        self.assertIsNotNone(history)
        self.assertEqual(history.request, request)
        self.assertEqual(history.old_status, STATUS_CREATED)
        self.assertEqual(history.new_status, STATUS_WAITING_SUPPLY)
        self.assertEqual(history.changed_by, self.user)
        self.assertEqual(history.comment, "Передано снабжению")
        self.assertEqual(RequestStatusHistory.objects.count(), 1)

    def test_allowed_status_transition_passes(self):
        request = self._create_request()

        change_request_status(request, STATUS_WAITING_SUPPLY, self.user, "Допустимый переход")
        request.refresh_from_db()

        self.assertEqual(request.status, STATUS_WAITING_SUPPLY)
        self.assertEqual(request.status_history.count(), 1)

    def test_disallowed_status_transition_is_blocked(self):
        request = self._create_request()

        with self.assertRaises(ValidationError):
            change_request_status(request, STATUS_DELIVERED, self.user, "Недопустимый переход")
        request.refresh_from_db()

        self.assertEqual(request.status, STATUS_CREATED)
        self.assertEqual(request.status_history.count(), 0)

    def test_problem_transition_is_available_from_active_statuses(self):
        active_statuses = [
            STATUS_CREATED,
            STATUS_WAITING_SUPPLY,
            STATUS_READY_TO_SHIP,
            STATUS_IN_TRANSIT,
        ]

        for status in active_statuses:
            with self.subTest(status=status):
                request = self._create_request(status=status)
                change_request_status(request, STATUS_PROBLEM, self.user, "Переход в проблему")
                request.refresh_from_db()

                self.assertEqual(request.status, STATUS_PROBLEM)

    def test_delivered_can_transition_to_closed(self):
        request = self._create_request(status=STATUS_DELIVERED)

        change_request_status(request, STATUS_CLOSED, self.user, "Заявка закрыта")
        request.refresh_from_db()

        self.assertEqual(request.status, STATUS_CLOSED)
        self.assertEqual(request.status_history.latest("created_at").old_status, STATUS_DELIVERED)
        self.assertEqual(request.status_history.latest("created_at").new_status, STATUS_CLOSED)

    def test_problem_report_can_be_created_and_request_moves_to_problem(self):
        request = self._create_request()

        problem = ProblemReport.objects.create(
            request=request,
            problem_type=ProblemReport.OTHER,
            description="Тестовая проблема",
            responsible_user=self.responsible,
            created_by=self.user,
        )
        change_request_status(request, STATUS_PROBLEM, self.user, "Зарегистрирована проблема")
        request.refresh_from_db()

        self.assertEqual(request.status, STATUS_PROBLEM)
        self.assertEqual(problem.problem_type, ProblemReport.OTHER)
        self.assertEqual(problem.status, ProblemReport.OPEN)
        self.assertEqual(request.problems.count(), 1)
        self.assertEqual(request.status_history.latest("created_at").new_status, STATUS_PROBLEM)

    def test_problem_can_be_closed(self):
        request = self._create_request(status=STATUS_PROBLEM)
        problem = ProblemReport.objects.create(
            request=request,
            problem_type=ProblemReport.DOCUMENT_MISMATCH,
            description="Несоответствие документов",
            responsible_user=self.responsible,
            created_by=self.user,
        )

        problem.status = ProblemReport.RESOLVED
        problem.resolved_at = timezone.now()
        problem.resolution_comment = "Документы исправлены"
        problem.save(update_fields=["status", "resolved_at", "resolution_comment"])
        change_request_status(request, STATUS_WAITING_SUPPLY, self.user, "Проблема закрыта")
        request.refresh_from_db()
        problem.refresh_from_db()

        self.assertEqual(problem.status, ProblemReport.RESOLVED)
        self.assertIsNotNone(problem.resolved_at)
        self.assertEqual(problem.resolution_comment, "Документы исправлены")
        self.assertEqual(request.status, STATUS_WAITING_SUPPLY)
        self.assertEqual(request.status_history.latest("created_at").new_status, STATUS_WAITING_SUPPLY)

    def test_attachment_can_be_uploaded_for_request(self):
        request = self._create_request()
        uploaded_file = SimpleUploadedFile(
            "invoice.pdf",
            b"%PDF-1.4 test file",
            content_type="application/pdf",
        )
        form = AttachmentForm(
            data={
                "file_type": Attachment.PDF_DOCUMENT,
                "description": "Тестовый PDF",
            },
            files={"file": uploaded_file},
        )

        self.assertTrue(form.is_valid(), form.errors.as_json())
        attachment = form.save(commit=False)
        attachment.request = request
        attachment.uploaded_by = self.user
        attachment.save()

        self.assertEqual(request.attachments.count(), 1)
        self.assertEqual(attachment.file_type, Attachment.PDF_DOCUMENT)
        self.assertEqual(attachment.uploaded_by, self.user)
        self.assertTrue(attachment.file.name.endswith(".pdf"))

    def test_attachment_form_allows_pdf_jpg_png_and_webp(self):
        request = self._create_request()
        files = [
            ("invoice.pdf", b"%PDF-1.4 test file", "application/pdf"),
            ("cargo.jpg", b"jpg test file", "image/jpeg"),
            ("cargo.png", b"png test file", "image/png"),
            ("cargo.webp", b"webp test file", "image/webp"),
        ]

        for file_name, content, content_type in files:
            with self.subTest(file_name=file_name):
                uploaded_file = SimpleUploadedFile(file_name, content, content_type=content_type)
                form = AttachmentForm(
                    data={
                        "file_type": Attachment.OTHER,
                        "description": "Тестовый файл",
                    },
                    files={"file": uploaded_file},
                )

                self.assertTrue(form.is_valid(), form.errors.as_json())
                attachment = form.save(commit=False)
                attachment.request = request
                attachment.uploaded_by = self.user
                attachment.save()

        self.assertEqual(request.attachments.count(), 4)

    def test_attachment_can_be_uploaded_from_request_card_and_displayed(self):
        request = self._create_request()
        self.client.force_login(self.user)
        uploaded_file = SimpleUploadedFile(
            "proof.png",
            b"png test file",
            content_type="image/png",
        )

        response = self.client.post(
            reverse("request_detail", kwargs={"pk": request.pk}),
            {
                "action": "attachment",
                "file_type": Attachment.CARGO_PHOTO,
                "description": "Фото груза",
                "file": uploaded_file,
            },
        )
        request.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(request.attachments.count(), 1)

        card_response = self.client.get(reverse("request_detail", kwargs={"pk": request.pk}))
        self.assertContains(card_response, "Фото груза")
        self.assertContains(card_response, "proof")

    def test_archivist_exports_requests_files_and_deletes_database_rows(self):
        old_datetime = timezone.now() - timedelta(days=181)
        first = self._create_request(client_name="Первый архивный клиент", created_at=old_datetime)
        second = self._create_request(client_name="Второй архивный клиент", created_at=old_datetime)

        first_file = Path(self.media_root) / "source-a" / "same.pdf"
        second_file = Path(self.media_root) / "source-b" / "same.pdf"
        first_file.parent.mkdir(parents=True, exist_ok=True)
        second_file.parent.mkdir(parents=True, exist_ok=True)
        first_file.write_bytes(b"first")
        second_file.write_bytes(b"second")
        Attachment.objects.create(
            request=first,
            file="source-a/same.pdf",
            file_type=Attachment.PDF_DOCUMENT,
            uploaded_by=self.user,
        )
        Attachment.objects.create(
            request=second,
            file="source-b/same.pdf",
            file_type=Attachment.PDF_DOCUMENT,
            uploaded_by=self.user,
        )

        result = archive_requests_for_date(old_datetime.date())

        self.assertEqual(result["requests"], 2)
        self.assertFalse(LogisticsRequest.objects.filter(id__in=[first.id, second.id]).exists())
        self.assertFalse(Attachment.objects.filter(request_id__in=[first.id, second.id]).exists())
        self.assertFalse(first_file.exists())
        self.assertFalse(second_file.exists())
        self.assertTrue(result["archive"].exists())
        self.assertEqual(result["archive"].name, f"{old_datetime:%d%m%Y}.zip")

        with zipfile.ZipFile(result["archive"]) as archive:
            names = archive.namelist()
            self.assertIn(f"{old_datetime:%Y-%m-%d}/requests.json", names)
            self.assertIn(f"{old_datetime:%Y-%m-%d}/files/same.pdf", names)
            self.assertIn(f"{old_datetime:%Y-%m-%d}/files/same_2.pdf", names)
            payload = archive.read(f"{old_datetime:%Y-%m-%d}/requests.json").decode("utf-8")

        self.assertIn("Первый архивный клиент", payload)
        self.assertIn("Второй архивный клиент", payload)

    def test_archivist_uses_retention_days_plus_one_day(self):
        due_datetime = timezone.now() - timedelta(days=181)
        fresh_datetime = timezone.now() - timedelta(days=180)
        due_request = self._create_request(client_name="Пора в архив", created_at=due_datetime)
        fresh_request = self._create_request(client_name="Ещё в работе", created_at=fresh_datetime)

        results = archive_due_requests(180)

        self.assertEqual(sum(result["requests"] for result in results), 1)
        self.assertFalse(LogisticsRequest.objects.filter(pk=due_request.pk).exists())
        self.assertTrue(LogisticsRequest.objects.filter(pk=fresh_request.pk).exists())


class LogisticsRoleAccessTests(TestCase):
    def setUp(self):
        self.roles = {}
        role_titles = {
            ROLE_ADMIN: "Администратор",
            ROLE_OPERATOR: "Оператор",
            ROLE_SUPPLY: "Снабжение",
            ROLE_TRANSPORT: "Транспорт",
            ROLE_WAREHOUSE: "Склад",
            ROLE_DRIVER: "Водитель",
            ROLE_MANAGER: "Руководитель",
        }
        for code, title in role_titles.items():
            self.roles[code] = Role.objects.create(code=code, title=title)

        self.admin = self._user("admin", ROLE_ADMIN, is_staff=True, is_superuser=True)
        self.operator = self._user("operator", ROLE_OPERATOR)
        self.manager_user = self._user("manager", ROLE_MANAGER)
        self.supply_user = self._user("supply", ROLE_SUPPLY)
        self.transport_user = self._user("transport", ROLE_TRANSPORT)
        self.warehouse_user = self._user("warehouse", ROLE_WAREHOUSE)
        self.driver_user = self._user("driver", ROLE_DRIVER)
        self.other_driver_user = self._user("other_driver", ROLE_DRIVER)

        self.client_record = Client.objects.create(
            name="Клиент",
            region="Москва",
            contact_name="Контакт",
            phone="+7 900 0",
        )
        self.warehouse = Warehouse.objects.create(name="Склад", region="Москва", address="Москва")
        self.vehicle = Vehicle.objects.create(
            name="ГАЗель",
            plate_number="А111АА777",
            max_weight_kg=1500,
            max_volume_m3=Decimal("10.000"),
            vehicle_type="фургон",
        )
        self.second_vehicle = Vehicle.objects.create(
            name="MAN",
            plate_number="В222ВВ777",
            max_weight_kg=5000,
            max_volume_m3=Decimal("32.000"),
            vehicle_type="грузовик",
        )
        self.driver, _ = Driver.objects.update_or_create(
            user=self.driver_user,
            defaults={"full_name": "Денис Водитель", "phone": "+7 900 1"},
        )
        self.other_driver, _ = Driver.objects.update_or_create(
            user=self.other_driver_user,
            defaults={"full_name": "Олег Водитель", "phone": "+7 900 2"},
        )

    def _user(self, username, role_code, **flags):
        user = get_user_model().objects.create_user(
            username=username,
            password="password",
            role=self.roles[role_code],
            **flags,
        )
        UserProfile.objects.update_or_create(
            user=user,
            defaults={"role": role_code, "phone": "", "telegram_id": "", "is_active": True},
        )
        return user

    def _request(self, **overrides):
        defaults = {
            "client_name": "Клиент",
            "client_address": "Адрес",
            "client_contact": "Контакт",
            "region": "Москва",
            "warehouse": self.warehouse,
            "cargo_description": "Груз",
            "cargo_places_count": 2,
            "cargo_weight_kg": Decimal("100.00"),
            "cargo_volume_m3": Decimal("1.000"),
            "dimensions_text": "2 коробки",
            "planned_ship_date": timezone.localdate(),
            "planned_delivery_date": timezone.localdate(),
            "created_by": self.operator,
        }
        defaults.update(overrides)
        return LogisticsRequest.objects.create(**defaults)

    def _edit_payload(self, request, **overrides):
        payload = {
            "request_number": request.request_number,
            "client": str(self.client_record.pk),
            "client_address": request.client_address,
            "client_contact": request.client_contact,
            "region": request.region,
            "warehouse": str(request.warehouse_id),
            "cargo_description": request.cargo_description,
            "cargo_places_count": str(request.cargo_places_count),
            "cargo_weight_kg": str(request.cargo_weight_kg),
            "cargo_volume_m3": str(request.cargo_volume_m3),
            "dimensions_text": request.dimensions_text,
            "supply_eta_date": request.supply_eta_date.isoformat() if request.supply_eta_date else "",
            "warehouse_arrival_date": request.warehouse_arrival_date.isoformat() if request.warehouse_arrival_date else "",
            "planned_ship_date": request.planned_ship_date.isoformat() if request.planned_ship_date else "",
            "actual_ship_date": request.actual_ship_date.isoformat() if request.actual_ship_date else "",
            "planned_delivery_date": request.planned_delivery_date.isoformat() if request.planned_delivery_date else "",
            "actual_delivery_date": request.actual_delivery_date.isoformat() if request.actual_delivery_date else "",
            "status": request.status,
            "priority": request.priority,
            "cz_status": request.cz_status,
            "cz_comment": request.cz_comment,
            "assigned_vehicle": str(request.assigned_vehicle_id or ""),
            "assigned_driver": str(request.assigned_driver_id or ""),
            "status_comment": "",
        }
        if request.cz_required:
            payload["cz_required"] = "on"
        if request.cz_checked:
            payload["cz_checked"] = "on"
        if request.cz_problem:
            payload["cz_problem"] = "on"
        if request.is_archived:
            payload["is_archived"] = "on"
        payload.update(overrides)
        return payload

    def test_driver_cannot_edit_other_driver_request(self):
        request = self._request(assigned_driver=self.other_driver, assigned_vehicle=self.vehicle)
        self.client.force_login(self.driver_user)

        response = self.client.get(reverse("request_edit", kwargs={"pk": request.pk}))

        self.assertEqual(response.status_code, 403)

    def test_warehouse_can_change_cz_fields(self):
        request = self._request(status=STATUS_WAITING_SUPPLY, cz_required=True, cz_status=LogisticsRequest.CZ_PENDING)
        self.client.force_login(self.warehouse_user)

        response = self.client.post(
            reverse("request_edit", kwargs={"pk": request.pk}),
            self._edit_payload(
                request,
                cz_required="on",
                cz_checked="on",
                cz_status=LogisticsRequest.CZ_OK,
                cz_comment="ЧЗ проверен складом",
            ),
        )
        request.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertTrue(request.cz_checked)
        self.assertEqual(request.cz_status, LogisticsRequest.CZ_OK)
        self.assertEqual(request.cz_comment, "ЧЗ проверен складом")

    def test_transport_can_assign_vehicle_and_driver(self):
        request = self._request(status=STATUS_READY_TO_SHIP)
        self.client.force_login(self.transport_user)

        response = self.client.post(
            reverse("request_edit", kwargs={"pk": request.pk}),
            self._edit_payload(
                request,
                assigned_vehicle=str(self.vehicle.pk),
                assigned_driver=str(self.driver.pk),
            ),
        )
        request.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(request.assigned_vehicle, self.vehicle)
        self.assertEqual(request.assigned_driver, self.driver)

    def test_supply_can_change_arrival_date_from_request_card(self):
        request = self._request()
        new_date = timezone.localdate() + timedelta(days=2)
        self.client.force_login(self.supply_user)

        page = self.client.get(reverse("request_detail", kwargs={"pk": request.pk}))
        self.assertContains(page, "Дата поступления")

        response = self.client.post(
            reverse("request_detail", kwargs={"pk": request.pk}),
            {"action": "supply_date", "supply_eta_date": new_date.isoformat()},
        )
        request.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(request.supply_eta_date, new_date)
        self.assertEqual(request.status, STATUS_WAITING_ARRIVAL)
        self.assertTrue(Notification.objects.filter(recipient_role=ROLE_WAREHOUSE, request=request).exists())

    def test_supply_can_set_cz_required_from_request_card(self):
        request = self._request(cz_required=False, cz_status=LogisticsRequest.CZ_NOT_REQUIRED)
        self.client.force_login(self.supply_user)

        page = self.client.get(reverse("request_detail", kwargs={"pk": request.pk}))
        self.assertContains(page, "Честный Знак")

        response = self.client.post(
            reverse("request_detail", kwargs={"pk": request.pk}),
            {"action": "supply_cz", "cz_required": "yes"},
        )
        request.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertTrue(request.cz_required)
        self.assertEqual(request.cz_status, LogisticsRequest.CZ_PENDING)

    def test_transport_can_assign_vehicle_and_driver_from_request_card(self):
        request = self._request(status=STATUS_READY_TO_SHIP)
        self.client.force_login(self.transport_user)

        page = self.client.get(reverse("request_detail", kwargs={"pk": request.pk}))
        self.assertContains(page, "Назначить транспорт")

        response = self.client.post(
            reverse("request_detail", kwargs={"pk": request.pk}),
            {
                "action": "assign_transport",
                "assigned_vehicle": str(self.vehicle.pk),
                "assigned_driver": str(self.driver.pk),
            },
        )
        request.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(request.assigned_vehicle, self.vehicle)
        self.assertEqual(request.assigned_driver, self.driver)

    def test_warehouse_can_change_warehouse_status_from_request_card(self):
        request = self._request(status=STATUS_WAITING_ARRIVAL)
        self.client.force_login(self.warehouse_user)

        page = self.client.get(reverse("request_detail", kwargs={"pk": request.pk}))
        self.assertContains(page, "Складской статус")

        response = self.client.post(
            reverse("request_detail", kwargs={"pk": request.pk}),
            {"action": "warehouse_status", "new_status": STATUS_IN_WAREHOUSE},
        )
        request.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(request.status, STATUS_IN_WAREHOUSE)
        self.assertTrue(
            RequestStatusHistory.objects.filter(
                request=request,
                old_status=STATUS_WAITING_ARRIVAL,
                new_status=STATUS_IN_WAREHOUSE,
                changed_by=self.warehouse_user,
                comment="Статус изменён складом",
            ).exists()
        )

    def test_warehouse_sets_ship_date_and_notifies_transport(self):
        request = self._request(status=STATUS_WAITING_ARRIVAL, planned_ship_date=None)
        ship_date = timezone.localdate() + timedelta(days=3)
        self.client.force_login(self.warehouse_user)

        response = self.client.post(
            reverse("request_detail", kwargs={"pk": request.pk}),
            {
                "action": "warehouse_status",
                "new_status": STATUS_IN_WAREHOUSE,
                "planned_ship_date": ship_date.isoformat(),
            },
        )
        request.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(request.planned_ship_date, ship_date)
        self.assertTrue(Notification.objects.filter(recipient_role=ROLE_TRANSPORT, request=request).exists())

    def test_operator_can_create_request(self):
        new_client = Client.objects.create(
            name="Новый клиент",
            region="Казань",
            contact_name="Новый контакт",
            phone="+7 900 123-45-67",
        )
        self.client.force_login(self.operator)

        response = self.client.post(
            reverse("request_create"),
            {
                "client": str(new_client.pk),
                "client_address": "Новый адрес",
                "warehouse": str(self.warehouse.pk),
                "cargo_description": "Новый груз",
                "cargo_places_count": "5",
                "cargo_weight_kg": "300.00",
                "cargo_volume_m3": "2.500",
                "dimensions_text": "5 коробок",
                "supply_eta_date": timezone.localdate().isoformat(),
                "planned_ship_date": timezone.localdate().isoformat(),
                "planned_delivery_date": timezone.localdate().isoformat(),
                "cz_required": "on",
                "cz_comment": "Нужна проверка ЧЗ",
            },
        )

        self.assertEqual(response.status_code, 302)
        created_request = LogisticsRequest.objects.get(client_name="Новый клиент", created_by=self.operator)
        self.assertEqual(created_request.status, STATUS_WAITING_SUPPLY)
        self.assertTrue(Notification.objects.filter(recipient_role=ROLE_SUPPLY, request=created_request).exists())

    def test_operator_can_manage_clients(self):
        self.client.force_login(self.operator)

        list_response = self.client.get(reverse("client_list"))
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "Добавить клиента")

        create_response = self.client.post(
            reverse("client_create"),
            {
                "name": "Новый справочник",
                "region": "Тула",
                "contact_name": "Анна",
                "phone": "+7 900 555-55-55",
                "email": "client@example.com",
            },
        )
        client_obj = Client.objects.get(name="Новый справочник")
        self.assertEqual(create_response.status_code, 302)
        self.assertEqual(client_obj.region, "Тула")

        edit_response = self.client.post(
            reverse("client_edit", kwargs={"pk": client_obj.pk}),
            {
                "name": "Обновленный справочник",
                "region": "Рязань",
                "contact_name": "Борис",
                "phone": "+7 900 666-66-66",
                "email": "updated@example.com",
            },
        )
        client_obj.refresh_from_db()
        self.assertEqual(edit_response.status_code, 302)
        self.assertEqual(client_obj.name, "Обновленный справочник")
        self.assertEqual(client_obj.region, "Рязань")

        delete_response = self.client.post(reverse("client_delete", kwargs={"pk": client_obj.pk}))
        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(Client.objects.filter(pk=client_obj.pk).exists())

    def test_driver_cannot_manage_clients(self):
        self.client.force_login(self.driver_user)

        response = self.client.get(reverse("client_list"))

        self.assertEqual(response.status_code, 403)

    def test_unavailable_edit_fields_are_hidden_for_operator(self):
        request = self._request(status=STATUS_CREATED)
        self.client.force_login(self.operator)

        response = self.client.get(reverse("request_edit", kwargs={"pk": request.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Недоступно для вашей роли")
        self.assertNotContains(response, "Номер заявки")
        self.assertNotContains(response, "Статус")
        self.assertNotContains(response, "Регион")
        self.assertNotContains(response, "Склад")
        self.assertNotContains(response, "Плановая дата поступления от снабжения")
        self.assertNotContains(response, "Плановая дата отгрузки")
        self.assertNotContains(response, "Честный Знак")
        self.assertContains(response, "Клиент")

    def test_only_admin_can_edit_delivered_request(self):
        request = self._request(status=STATUS_DELIVERED)

        self.client.force_login(self.operator)
        detail_response = self.client.get(reverse("request_detail", kwargs={"pk": request.pk}))
        edit_response = self.client.get(reverse("request_edit", kwargs={"pk": request.pk}))

        self.assertEqual(detail_response.status_code, 200)
        self.assertNotContains(detail_response, "Редактировать")
        self.assertEqual(edit_response.status_code, 403)

        self.client.force_login(self.admin)
        admin_detail_response = self.client.get(reverse("request_detail", kwargs={"pk": request.pk}))
        admin_edit_response = self.client.get(reverse("request_edit", kwargs={"pk": request.pk}))

        self.assertContains(admin_detail_response, "Редактировать")
        self.assertEqual(admin_edit_response.status_code, 200)

    def test_operator_create_form_hides_service_fields(self):
        self.client.force_login(self.operator)

        response = self.client.get(reverse("request_create"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Склад")
        self.assertNotContains(response, "Регион")
        self.assertNotContains(response, "Плановая дата поступления от снабжения")
        self.assertNotContains(response, "Плановая дата отгрузки")
        self.assertNotContains(response, "Честный Знак")
        self.assertContains(response, "Клиент")

    def test_operator_can_save_visible_fields_when_transport_is_already_assigned(self):
        updated_client = Client.objects.create(name="Оператор обновил клиента", region="Москва")
        request = self._request(
            status=STATUS_READY_TO_SHIP,
            assigned_vehicle=self.vehicle,
            assigned_driver=self.driver,
        )
        self.client.force_login(self.operator)

        response = self.client.post(
            reverse("request_edit", kwargs={"pk": request.pk}),
            {
                "client": str(updated_client.pk),
                "client_address": request.client_address,
                "client_contact": request.client_contact,
                "region": request.region,
                "warehouse": str(request.warehouse_id),
                "cargo_description": request.cargo_description,
                "cargo_places_count": str(request.cargo_places_count),
                "cargo_weight_kg": str(request.cargo_weight_kg),
                "cargo_volume_m3": str(request.cargo_volume_m3),
                "dimensions_text": request.dimensions_text,
                "supply_eta_date": request.supply_eta_date.isoformat() if request.supply_eta_date else "",
                "planned_ship_date": request.planned_ship_date.isoformat() if request.planned_ship_date else "",
                "planned_delivery_date": request.planned_delivery_date.isoformat() if request.planned_delivery_date else "",
                "priority": request.priority,
                "cz_comment": request.cz_comment,
            },
        )
        request.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(request.client_name, "Оператор обновил клиента")
        self.assertEqual(request.assigned_vehicle, self.vehicle)
        self.assertEqual(request.assigned_driver, self.driver)

    def test_operator_can_skip_supply_when_goods_are_reserved_in_warehouse(self):
        warehouse_client = Client.objects.create(name="Клиент со склада", region="Москва")
        self.client.force_login(self.operator)

        response = self.client.post(
            reverse("request_create"),
            {
                "client": str(warehouse_client.pk),
                "client_address": "Адрес",
                "warehouse": str(self.warehouse.pk),
                "cargo_description": "Зарезервированный груз",
                "skip_supply_to_warehouse": "on",
                "planned_ship_date": timezone.localdate().isoformat(),
                "planned_delivery_date": timezone.localdate().isoformat(),
            },
        )
        created_request = LogisticsRequest.objects.get(client_name="Клиент со склада", created_by=self.operator)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(created_request.status, STATUS_IN_WAREHOUSE)
        self.assertEqual(created_request.warehouse_arrival_date, timezone.localdate())
        self.assertTrue(Notification.objects.filter(recipient_role=ROLE_WAREHOUSE, request=created_request).exists())

    def test_admin_can_edit_fields_from_all_role_areas(self):
        admin_client = Client.objects.create(name="Админ изменил клиента", region="Москва")
        request = self._request(status=STATUS_CREATED, cz_required=False)
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("request_edit", kwargs={"pk": request.pk}),
            self._edit_payload(
                request,
                client=str(admin_client.pk),
                cz_required="on",
                cz_checked="on",
                cz_status=LogisticsRequest.CZ_OK,
                assigned_vehicle=str(self.second_vehicle.pk),
                assigned_driver=str(self.driver.pk),
                status=STATUS_WAITING_SUPPLY,
                is_archived="on",
                status_comment="Админ сменил статус",
            ),
        )
        request.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(request.client_name, "Админ изменил клиента")
        self.assertTrue(request.cz_required)
        self.assertTrue(request.cz_checked)
        self.assertEqual(request.assigned_vehicle, self.second_vehicle)
        self.assertEqual(request.assigned_driver, self.driver)
        self.assertEqual(request.status, STATUS_WAITING_SUPPLY)
        self.assertTrue(request.is_archived)

    def test_admin_assigns_driver_and_driver_marks_delivered(self):
        own_request = self._request(assigned_vehicle=self.vehicle)
        other_request = self._request(client_name="Чужая заявка", assigned_driver=self.other_driver, assigned_vehicle=self.second_vehicle)

        self.client.force_login(self.admin)
        assign_response = self.client.post(
            reverse("request_detail", kwargs={"pk": own_request.pk}),
            {"action": "assign_driver", "assigned_driver": str(self.driver.pk)},
        )
        own_request.refresh_from_db()

        self.assertEqual(assign_response.status_code, 302)
        self.assertEqual(own_request.assigned_driver, self.driver)

        self.client.force_login(self.driver_user)
        list_response = self.client.get(reverse("request_list"))

        self.assertContains(list_response, "Мои доставки")
        self.assertContains(list_response, own_request.request_number)
        self.assertNotContains(list_response, other_request.request_number)
        detail_response = self.client.get(reverse("request_detail", kwargs={"pk": own_request.pk}))
        self.assertContains(detail_response, "Режим водителя")
        self.assertContains(detail_response, "Доставлено")
        self.assertEqual(self.client.get(reverse("request_detail", kwargs={"pk": other_request.pk})).status_code, 403)

        response = self.client.post(
            reverse("request_detail", kwargs={"pk": own_request.pk}),
            {"action": "driver_delivered"},
        )
        own_request.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(own_request.status, STATUS_DELIVERED)
        self.assertEqual(own_request.actual_delivery_date, timezone.localdate())
        self.assertTrue(
            RequestStatusHistory.objects.filter(
                request=own_request,
                old_status=STATUS_CREATED,
                new_status=STATUS_DELIVERED,
                changed_by=self.driver_user,
            ).exists()
        )

    def test_status_change_in_django_admin_creates_history(self):
        request_obj = self._request(status=STATUS_CREATED)
        request_obj.status = STATUS_WAITING_SUPPLY
        model_admin = LogisticsRequestAdmin(LogisticsRequest, django_admin.site)

        class DummyRequest:
            user = self.admin

        model_admin.save_model(DummyRequest(), request_obj, form=None, change=True)
        request_obj.refresh_from_db()

        self.assertEqual(request_obj.status, STATUS_WAITING_SUPPLY)
        self.assertTrue(
            RequestStatusHistory.objects.filter(
                request=request_obj,
                old_status=STATUS_CREATED,
                new_status=STATUS_WAITING_SUPPLY,
                changed_by=self.admin,
                comment="Статус изменён через админку",
            ).exists()
        )

    def test_user_can_create_problem_from_request_card(self):
        request_obj = self._request(status=STATUS_CREATED)
        self.client.force_login(self.operator)

        detail_response = self.client.get(reverse("request_detail", kwargs={"pk": request_obj.pk}))
        self.assertContains(detail_response, "Проблема")

        response = self.client.post(
            reverse("request_detail", kwargs={"pk": request_obj.pk}),
            {
                "action": "problem",
                "problem_type": ProblemReport.OTHER,
                "description": "Повреждена часть груза",
                "responsible_user": str(self.admin.pk),
            },
        )
        request_obj.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(request_obj.status, STATUS_PROBLEM)
        self.assertTrue(
            ProblemReport.objects.filter(
                request=request_obj,
                problem_type=ProblemReport.OTHER,
                description="Повреждена часть груза",
                responsible_user=self.admin,
                created_by=self.operator,
            ).exists()
        )
        self.assertTrue(
            RequestStatusHistory.objects.filter(
                request=request_obj,
                old_status=STATUS_CREATED,
                new_status=STATUS_PROBLEM,
                changed_by=self.operator,
                comment="Зарегистрирована проблема",
            ).exists()
        )

        card_response = self.client.get(reverse("request_detail", kwargs={"pk": request_obj.pk}))
        self.assertContains(card_response, "Повреждена часть груза")

    def test_calendar_shows_requests_by_delivery_date(self):
        request_obj = self._request(client_name="Клиент календаря", planned_delivery_date=timezone.localdate())
        self.client.force_login(self.admin)

        list_response = self.client.get(reverse("request_list"))
        response = self.client.get(reverse("request_calendar"))

        self.assertContains(list_response, "Календарь")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Календарь")
        self.assertContains(response, "Назад")
        self.assertContains(response, "Вперед")
        self.assertContains(response, "Клиент календаря")
        self.assertContains(response, request_obj.get_absolute_url())

    def test_calendar_uses_supply_date_for_supply_stage(self):
        supply_date = timezone.localdate() + timedelta(days=8)
        request_obj = self._request(
            client_name="Клиент снабжения в календаре",
            status=STATUS_WAITING_ARRIVAL,
            supply_eta_date=supply_date,
            planned_delivery_date=None,
            planned_ship_date=None,
        )
        self.client.force_login(self.transport_user)

        response = self.client.get(f"{reverse('request_calendar')}?month={supply_date:%Y-%m}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Клиент снабжения в календаре")
        self.assertContains(response, request_obj.get_absolute_url())
        self.assertContains(response, "calendar-request-supply")
