from datetime import date

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.constants import (ROLE_ADMIN, ROLE_DRIVER, ROLE_OPERATOR,
                                    ROLE_SUPPLY, ROLE_TRANSPORT,
                                    ROLE_WAREHOUSE)
from apps.accounts.models import UserProfile
from apps.checklists.models import (
    ChecklistTemplate,
    ChecklistTemplateItem,
    RequestChecklistItem,
    UserTask,
)
from apps.checklists.services import create_checklist_for_request
from apps.logistics.models import Client, LogisticsRequest, Warehouse


class ChecklistTemplateModelTests(TestCase):
    def test_str_returns_name_when_set(self):
        tpl, _ = ChecklistTemplate.objects.get_or_create(role=ROLE_DRIVER, defaults={"name": "Чек-лист водителя"})
        self.assertEqual(str(tpl), "Чек-лист водителя")

    def test_str_falls_back_to_role_display(self):
        tpl, _ = ChecklistTemplate.objects.get_or_create(role=ROLE_TRANSPORT, defaults={"name": ""})
        self.assertIn("Транспорт", str(tpl))


class CreateChecklistForRequestTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="op_cl3", password="password")
        UserProfile.objects.update_or_create(user=self.user, defaults={"role": ROLE_OPERATOR, "is_active": True})
        self.warehouse = Warehouse.objects.create(name="WH", region="MSK", address="addr")
        self.request = LogisticsRequest.objects.create(
            client_name="Client", client_address="addr", client_contact="C",
            region="MSK", warehouse=self.warehouse, cargo_description="c",
            cargo_places_count=1, cargo_weight_kg=10, cargo_volume_m3=0.1,
            dimensions_text="1", planned_ship_date="2025-01-01",
            planned_delivery_date="2025-01-01", created_by=self.user,
        )

    def test_creates_checklist_items_from_active_templates(self):
        tpl, _ = ChecklistTemplate.objects.get_or_create(role="manager", defaults={"is_active": True})
        tpl.is_active = True
        tpl.save()
        ChecklistTemplateItem.objects.create(template=tpl, text="Пункт 1", order=1, is_active=True)
        ChecklistTemplateItem.objects.create(template=tpl, text="Пункт 2", order=2, is_active=True)

        count = create_checklist_for_request(self.request)

        self.assertEqual(count, 2)
        self.assertEqual(RequestChecklistItem.objects.filter(request=self.request).count(), 2)

    def test_is_idempotent_second_call_returns_zero(self):
        tpl, _ = ChecklistTemplate.objects.get_or_create(role="viewer", defaults={"is_active": True})
        tpl.is_active = True
        tpl.save()
        ChecklistTemplateItem.objects.create(template=tpl, text="Item", order=1, is_active=True)

        create_checklist_for_request(self.request)
        count = create_checklist_for_request(self.request)

        self.assertEqual(count, 0)

    def test_skips_inactive_template(self):
        tpl, _ = ChecklistTemplate.objects.get_or_create(role="manager", defaults={"is_active": False})
        tpl.is_active = False
        tpl.save()
        # delete existing items to avoid stale data
        ChecklistTemplateItem.objects.filter(template=tpl).delete()

        count = create_checklist_for_request(self.request)

        self.assertEqual(count, 0)

    def test_skips_inactive_template_items(self):
        tpl, _ = ChecklistTemplate.objects.get_or_create(role=ROLE_OPERATOR, defaults={"is_active": True})
        tpl.is_active = True
        tpl.save()
        ChecklistTemplateItem.objects.filter(template=tpl).delete()
        ChecklistTemplateItem.objects.create(template=tpl, text="Active", order=1, is_active=True)
        ChecklistTemplateItem.objects.create(template=tpl, text="Inactive", order=2, is_active=False)

        count = create_checklist_for_request(self.request)

        self.assertEqual(count, 1)


class RequestChecklistItemTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="op_ci3", password="password")
        UserProfile.objects.update_or_create(user=self.user, defaults={"role": ROLE_OPERATOR, "is_active": True})
        self.warehouse = Warehouse.objects.create(name="WH", region="MSK", address="addr")
        self.request = LogisticsRequest.objects.create(
            client_name="Client", client_address="addr", client_contact="C",
            region="MSK", warehouse=self.warehouse, cargo_description="c",
            cargo_places_count=1, cargo_weight_kg=10, cargo_volume_m3=0.1,
            dimensions_text="1", planned_ship_date="2025-01-01",
            planned_delivery_date="2025-01-01", created_by=self.user,
        )

    def test_str_truncates_long_text(self):
        item = RequestChecklistItem.objects.create(
            request=self.request, role=ROLE_OPERATOR,
            text="A" * 100, order=1,
        )
        self.assertLessEqual(len(str(item)), 71)


class UserTaskModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tasker3", password="password")

    def test_is_overdue_true_when_past_due_and_not_done(self):
        task = UserTask.objects.create(
            user=self.user, text="Old task",
            due_date=timezone.localdate() - timezone.timedelta(days=1),
            is_done=False,
        )
        self.assertTrue(task.is_overdue)

    def test_is_overdue_false_when_done(self):
        task = UserTask.objects.create(
            user=self.user, text="Done task",
            due_date=timezone.localdate() - timezone.timedelta(days=10),
            is_done=True,
        )
        self.assertFalse(task.is_overdue)

    def test_is_overdue_false_when_no_due_date(self):
        task = UserTask.objects.create(user=self.user, text="No date", due_date=None, is_done=False)
        self.assertFalse(task.is_overdue)

    def test_is_overdue_false_when_due_today(self):
        task = UserTask.objects.create(
            user=self.user, text="Today", due_date=timezone.localdate(), is_done=False,
        )
        self.assertFalse(task.is_overdue)

    def test_is_overdue_false_when_due_future(self):
        task = UserTask.objects.create(
            user=self.user, text="Future",
            due_date=timezone.localdate() + timezone.timedelta(days=5),
            is_done=False,
        )
        self.assertFalse(task.is_overdue)


class ChecklistItemToggleViewTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(username="admin_tgl3", password="password")
        UserProfile.objects.update_or_create(user=self.admin, defaults={"role": ROLE_ADMIN, "is_active": True})

        self.operator = get_user_model().objects.create_user(username="op_tgl3", password="password")
        UserProfile.objects.update_or_create(user=self.operator, defaults={"role": ROLE_OPERATOR, "is_active": True})

        self.supply = get_user_model().objects.create_user(username="sup_tgl3", password="password")
        UserProfile.objects.update_or_create(user=self.supply, defaults={"role": ROLE_SUPPLY, "is_active": True})

        self.warehouse = Warehouse.objects.create(name="WH", region="MSK", address="addr")
        self.request = LogisticsRequest.objects.create(
            client_name="Client", client_address="addr", client_contact="C",
            region="MSK", warehouse=self.warehouse, cargo_description="c",
            cargo_places_count=1, cargo_weight_kg=10, cargo_volume_m3=0.1,
            dimensions_text="1", planned_ship_date="2025-01-01",
            planned_delivery_date="2025-01-01", created_by=self.operator,
        )
        self.item = RequestChecklistItem.objects.create(
            request=self.request, role=ROLE_OPERATOR, text="Test item", order=1,
        )

    def test_admin_can_toggle_any_role_item(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("checklists:item_toggle", kwargs={"item_pk": self.item.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_done"])

    def test_own_role_can_toggle(self):
        self.client.force_login(self.operator)
        response = self.client.post(reverse("checklists:item_toggle", kwargs={"item_pk": self.item.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_done"])

    def test_other_role_cannot_toggle(self):
        self.client.force_login(self.supply)
        response = self.client.post(reverse("checklists:item_toggle", kwargs={"item_pk": self.item.pk}))
        self.assertEqual(response.status_code, 403)

    def test_toggle_sets_checked_by_and_checked_at(self):
        self.client.force_login(self.operator)
        response = self.client.post(reverse("checklists:item_toggle", kwargs={"item_pk": self.item.pk}))
        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertTrue(self.item.is_done)
        self.assertEqual(self.item.checked_by, self.operator)
        self.assertIsNotNone(self.item.checked_at)

    def test_untoggle_clears_checked_by_and_checked_at(self):
        self.item.is_done = True
        self.item.checked_by = self.operator
        self.item.checked_at = timezone.now()
        self.item.save()
        self.client.force_login(self.operator)
        response = self.client.post(reverse("checklists:item_toggle", kwargs={"item_pk": self.item.pk}))
        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_done)
        self.assertIsNone(self.item.checked_by)
        self.assertIsNone(self.item.checked_at)


class UserTaskViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tasker_v3", password="password")
        UserProfile.objects.update_or_create(user=self.user, defaults={"role": ROLE_OPERATOR, "is_active": True})

    def test_create_task(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("checklists:user_task_create"), {"text": "New task"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(UserTask.objects.filter(user=self.user, text="New task").exists())

    def test_create_task_with_due_date(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("checklists:user_task_create"), {"text": "Dated task", "due_date": "2025-12-31"})
        self.assertEqual(response.status_code, 200)
        task = UserTask.objects.get(user=self.user, text="Dated task")
        self.assertEqual(task.due_date, date(2025, 12, 31))

    def test_create_task_empty_text_fails(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("checklists:user_task_create"), {"text": "  "})
        self.assertEqual(response.status_code, 400)

    def test_create_task_invalid_date_fails(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("checklists:user_task_create"), {"text": "Bad date", "due_date": "not-a-date"})
        self.assertEqual(response.status_code, 400)

    def test_toggle_task(self):
        task = UserTask.objects.create(user=self.user, text="Toggle me")
        self.client.force_login(self.user)
        response = self.client.post(reverse("checklists:user_task_toggle", kwargs={"task_pk": task.pk}))
        task.refresh_from_db()
        self.assertTrue(task.is_done)
        self.assertIsNotNone(task.done_at)

    def test_delete_task(self):
        task = UserTask.objects.create(user=self.user, text="Delete me")
        self.client.force_login(self.user)
        response = self.client.post(reverse("checklists:user_task_delete", kwargs={"task_pk": task.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(UserTask.objects.filter(pk=task.pk).exists())


class CurrentTasksViewTests(TestCase):
    def setUp(self):
        self.operator = get_user_model().objects.create_user(username="ct_op4", password="password")
        UserProfile.objects.update_or_create(user=self.operator, defaults={"role": ROLE_OPERATOR, "is_active": True})

        self.operator2 = get_user_model().objects.create_user(username="ct_op5", password="password")
        UserProfile.objects.update_or_create(user=self.operator2, defaults={"role": ROLE_OPERATOR, "is_active": True})

        self.warehouse = Warehouse.objects.create(name="WH", region="MSK", address="addr")
        self.request_mine = LogisticsRequest.objects.create(
            client_name="My Client", client_address="addr", client_contact="C",
            region="MSK", warehouse=self.warehouse, cargo_description="c",
            cargo_places_count=1, cargo_weight_kg=10, cargo_volume_m3=0.1,
            dimensions_text="1", planned_ship_date="2025-01-01",
            planned_delivery_date="2025-01-01", created_by=self.operator,
        )
        self.request_other = LogisticsRequest.objects.create(
            client_name="Other Client", client_address="addr2", client_contact="C2",
            region="MSK", warehouse=self.warehouse, cargo_description="c",
            cargo_places_count=1, cargo_weight_kg=10, cargo_volume_m3=0.1,
            dimensions_text="1", planned_ship_date="2025-01-01",
            planned_delivery_date="2025-01-01", created_by=self.operator2,
        )

    def test_operator_sees_only_own_requests(self):
        RequestChecklistItem.objects.create(request=self.request_mine, role=ROLE_OPERATOR, text="Mine", order=1, is_done=False)
        RequestChecklistItem.objects.create(request=self.request_other, role=ROLE_OPERATOR, text="Other", order=1, is_done=False)
        self.client.force_login(self.operator)
        response = self.client.get(reverse("checklists:current_tasks"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My Client")
        self.assertNotContains(response, "Other Client")

    def test_empty_page_when_no_tasks(self):
        self.client.force_login(self.operator)
        response = self.client.get(reverse("checklists:current_tasks"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["blocks"]), 0)


class CurrentTasksCountContextProcessorTests(TestCase):
    def setUp(self):
        self.operator = get_user_model().objects.create_user(username="cp_op5", password="password")
        UserProfile.objects.update_or_create(user=self.operator, defaults={"role": ROLE_OPERATOR, "is_active": True})
        self.operator2 = get_user_model().objects.create_user(username="cp_op6", password="password")
        UserProfile.objects.update_or_create(user=self.operator2, defaults={"role": ROLE_OPERATOR, "is_active": True})
        self.warehouse = Warehouse.objects.create(name="WH", region="MSK", address="addr")

    def test_counts_only_own_requests_for_operator(self):
        from apps.checklists.context_processors import current_tasks_count
        request_mine = LogisticsRequest.objects.create(
            client_name="My", client_address="a", client_contact="c",
            region="MSK", warehouse=self.warehouse, cargo_description="d",
            cargo_places_count=1, cargo_weight_kg=1, cargo_volume_m3=0.1,
            dimensions_text="1", planned_ship_date="2025-01-01",
            planned_delivery_date="2025-01-01", created_by=self.operator,
        )
        request_other = LogisticsRequest.objects.create(
            client_name="Other", client_address="b", client_contact="c2",
            region="MSK", warehouse=self.warehouse, cargo_description="d",
            cargo_places_count=1, cargo_weight_kg=1, cargo_volume_m3=0.1,
            dimensions_text="1", planned_ship_date="2025-01-01",
            planned_delivery_date="2025-01-01", created_by=self.operator2,
        )
        RequestChecklistItem.objects.create(request=request_mine, role=ROLE_OPERATOR, text="t", order=1, is_done=False)
        RequestChecklistItem.objects.create(request=request_other, role=ROLE_OPERATOR, text="t", order=1, is_done=False)
        req = RequestFactory().get("/")
        req.user = self.operator
        result = current_tasks_count(req)
        self.assertEqual(result["current_tasks_count"], 1)

    def test_includes_user_task_count(self):
        from apps.checklists.context_processors import current_tasks_count
        UserTask.objects.create(user=self.operator, text="Personal", is_done=False)
        req = RequestFactory().get("/")
        req.user = self.operator
        result = current_tasks_count(req)
        self.assertEqual(result["current_tasks_count"], 1)
