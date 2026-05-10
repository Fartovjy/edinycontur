from django.contrib.auth.decorators import login_required
from django.db.models import Exists, OuterRef, Q
from django.shortcuts import render
from django.utils import timezone

from apps.accounts.constants import ROLE_ADMIN, ROLE_MANAGER
from apps.accounts.permissions import role_required
from apps.logistics.constants import (
    STATUS_CANCELLED,
    STATUS_CLOSED,
    STATUS_DELIVERED,
    STATUS_PROBLEM,
)
from apps.logistics.models import LogisticsRequest
from apps.problems.models import ProblemReport


@login_required
@role_required(ROLE_ADMIN, ROLE_MANAGER)
def manager_dashboard(request):
    today = timezone.localdate()
    open_problem_qs = ProblemReport.objects.filter(
        request=OuterRef("pk"),
        status__in=[ProblemReport.OPEN, ProblemReport.IN_PROGRESS],
    )
    requests = (
        LogisticsRequest.objects.filter(is_archived=False)
        .select_related("warehouse", "assigned_driver", "assigned_vehicle")
        .annotate(has_open_problem=Exists(open_problem_qs))
    )
    active_requests = requests.exclude(status__in=[STATUS_DELIVERED, STATUS_CLOSED, STATUS_CANCELLED])

    problem_requests = active_requests.filter(Q(status=STATUS_PROBLEM) | Q(has_open_problem=True))
    delivered_today = requests.filter(status=STATUS_DELIVERED, actual_delivery_date=today)
    without_driver = active_requests.filter(assigned_driver__isnull=True)
    overdue = active_requests.filter(planned_delivery_date__lt=today)

    open_problems = (
        ProblemReport.objects.filter(status__in=[ProblemReport.OPEN, ProblemReport.IN_PROGRESS])
        .select_related("request", "responsible_user")
        .order_by("-created_at")[:10]
    )

    return render(
        request,
        "logistics/dashboard.html",
        {
            "metrics": [
                {"title": "Активные заявки", "value": active_requests.count(), "tone": "primary"},
                {"title": "Проблемные", "value": problem_requests.count(), "tone": "danger"},
                {"title": "Доставленные сегодня", "value": delivered_today.count(), "tone": "success"},
                {"title": "Без водителя", "value": without_driver.count(), "tone": "warning"},
                {"title": "Просроченные", "value": overdue.count(), "tone": "secondary"},
            ],
            "active_requests": active_requests.order_by("-updated_at")[:10],
            "problem_requests": problem_requests.order_by("-updated_at")[:10],
            "delivered_today": delivered_today.order_by("-updated_at")[:10],
            "without_driver": without_driver.order_by("-updated_at")[:10],
            "overdue": overdue.order_by("planned_delivery_date")[:10],
            "open_problems": open_problems,
        },
    )
