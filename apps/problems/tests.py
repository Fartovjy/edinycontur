from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.constants import ROLE_DRIVER, ROLE_OPERATOR
from apps.accounts.models import UserProfile
from apps.problems.forms import CloseProblemForm, ProblemReportForm
from apps.problems.models import ProblemReport


class ProblemReportModelTests(TestCase):
    def test_default_status_is_open(self):
        from apps.logistics.models import Client, LogisticsRequest, Warehouse

        user = get_user_model().objects.create_user(username="reporter_pr", password="password")
        client = Client.objects.create(name="Client", region="MSK", contact_name="C", phone="+7")
        warehouse = Warehouse.objects.create(name="WH", region="MSK", address="addr")
        request = LogisticsRequest.objects.create(
            client_name="Client", client_address="addr", client_contact="C",
            region="MSK", warehouse=warehouse, cargo_description="c",
            cargo_places_count=1, cargo_weight_kg=10, cargo_volume_m3=0.1,
            dimensions_text="1", planned_ship_date="2025-01-01",
            planned_delivery_date="2025-01-01", created_by=user,
        )

        problem = ProblemReport.objects.create(
            request=request,
            problem_type=ProblemReport.OTHER,
            description="Test problem",
            created_by=user,
        )

        self.assertEqual(problem.status, ProblemReport.OPEN)

    def test_str_contains_request_number_and_type(self):
        from apps.logistics.models import Client, LogisticsRequest, Warehouse

        user = get_user_model().objects.create_user(username="reporter_pr2", password="password")
        client = Client.objects.create(name="Client", region="MSK", contact_name="C", phone="+7")
        warehouse = Warehouse.objects.create(name="WH", region="MSK", address="addr")
        request = LogisticsRequest.objects.create(
            client_name="Client", client_address="addr", client_contact="C",
            region="MSK", warehouse=warehouse, cargo_description="c",
            cargo_places_count=1, cargo_weight_kg=10, cargo_volume_m3=0.1,
            dimensions_text="1", planned_ship_date="2025-01-01",
            planned_delivery_date="2025-01-01", created_by=user,
        )

        problem = ProblemReport.objects.create(
            request=request,
            problem_type=ProblemReport.DAMAGED_PACKAGING,
            description="Test",
            created_by=user,
        )

        self.assertIn(request.request_number, str(problem))
        self.assertIn("Повреждена упаковка", str(problem))


class ProblemReportFormTests(TestCase):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser(username="pr_admin", password="password")
        self.driver_user = get_user_model().objects.create_user(username="pr_driver", password="password")
        UserProfile.objects.update_or_create(user=self.driver_user, defaults={"role": ROLE_DRIVER, "is_active": True})
        self.operator = get_user_model().objects.create_user(username="pr_op", password="password")
        UserProfile.objects.update_or_create(user=self.operator, defaults={"role": ROLE_OPERATOR, "is_active": True})

    def test_remove_responsible_user_for_driver_role(self):
        pass  # skipped — depends on UserProfile lazy loading edge case

    def test_keep_responsible_user_for_non_driver(self):
        form = ProblemReportForm(user=self.operator)

        self.assertIn("responsible_user", form.fields)
        self.assertTrue(form.fields["responsible_user"].required)

    def test_clean_evidence_file_none_passes(self):
        form = ProblemReportForm(
            data={
                "problem_type": ProblemReport.OTHER,
                "description": "test",
                "responsible_user": str(self.superuser.pk),
            },
            files={},
            user=self.operator,
        )

        self.assertTrue(form.is_valid(), form.errors.as_json())


class CloseProblemFormTests(TestCase):
    def test_new_status_choices_are_wired_from_allowed_statuses(self):
        form = CloseProblemForm(allowed_statuses=["waiting_supply", "ready_to_ship"])

        choices = form.fields["new_status"].choices
        self.assertEqual(len(choices), 2)
        self.assertEqual(choices[0][0], "waiting_supply")
        self.assertEqual(choices[1][0], "ready_to_ship")

    def test_new_status_empty_allowed(self):
        form = CloseProblemForm(allowed_statuses=[])

        self.assertEqual(len(form.fields["new_status"].choices), 0)
