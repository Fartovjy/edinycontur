import calendar as calendar_module
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.accounts.constants import ROLE_ADMIN, ROLE_DRIVER, ROLE_MANAGER, ROLE_OPERATOR, ROLE_SUPPLY, ROLE_TRANSPORT, ROLE_WAREHOUSE
from apps.accounts.permissions import can_change_status, can_create_problem, can_edit_request, get_user_role, role_required
from apps.documents.forms import AttachmentForm
from apps.documents.models import Attachment
from apps.notifications.services import create_role_notification
from apps.problems.forms import CloseProblemForm, ProblemReportForm
from apps.problems.models import ProblemReport
from apps.transport.models import Driver, Vehicle

from .constants import (
    STATUS_CHOICES,
    STATUS_CANCELLED,
    STATUS_CLOSED,
    STATUS_DELIVERED,
    STATUS_IN_TRANSIT,
    STATUS_IN_WAREHOUSE,
    STATUS_PROBLEM,
    STATUS_CREATED,
    STATUS_CZ_CHECK,
    STATUS_READY_TO_SHIP,
    STATUS_SHIPPED,
    STATUS_TRANSPORT_ASSIGNED,
    STATUS_WAITING_ARRIVAL,
    STATUS_WAITING_SUPPLY,
)
from .forms import ClientForm, LogisticsRequestCreateForm, LogisticsRequestForm
from .models import Client, LogisticsRequest, RequestStatusHistory, Warehouse
from .services import change_request_status, get_allowed_next_statuses


ALL_EDIT_FIELDS = set(LogisticsRequestForm.Meta.fields) | {"status_comment"}

OPERATOR_EDIT_FIELDS = {
    "client",
    "client_address",
    "client_contact",
    "cargo_description",
    "cargo_places_count",
    "cargo_weight_kg",
    "cargo_volume_m3",
    "dimensions_text",
    "planned_delivery_date",
    "priority",
}
SUPPLY_EDIT_FIELDS = {"supply_eta_date", "warehouse_arrival_date", "status", "status_comment"}
TRANSPORT_EDIT_FIELDS = {"assigned_vehicle", "assigned_driver", "planned_ship_date", "actual_ship_date", "status", "status_comment"}
WAREHOUSE_EDIT_FIELDS = {"warehouse_arrival_date", "actual_ship_date", "cz_required", "cz_checked", "cz_status", "cz_comment", "cz_problem", "status", "status_comment"}
DRIVER_EDIT_FIELDS = {"actual_delivery_date", "status", "status_comment"}
COMPLETED_STATUSES = {STATUS_DELIVERED, STATUS_CLOSED, STATUS_CANCELLED}

ROLE_STATUS_TARGETS = {
    ROLE_SUPPLY: {STATUS_WAITING_SUPPLY, STATUS_WAITING_ARRIVAL, STATUS_PROBLEM},
    ROLE_TRANSPORT: {STATUS_TRANSPORT_ASSIGNED, STATUS_SHIPPED, STATUS_PROBLEM},
    ROLE_WAREHOUSE: {STATUS_IN_WAREHOUSE, STATUS_CZ_CHECK, STATUS_READY_TO_SHIP, STATUS_SHIPPED, STATUS_PROBLEM},
    ROLE_DRIVER: {STATUS_IN_TRANSIT, STATUS_DELIVERED, STATUS_PROBLEM},
}

MONTH_NAMES = {
    1: "Январь",
    2: "Февраль",
    3: "Март",
    4: "Апрель",
    5: "Май",
    6: "Июнь",
    7: "Июль",
    8: "Август",
    9: "Сентябрь",
    10: "Октябрь",
    11: "Ноябрь",
    12: "Декабрь",
}

FIXED_HOLIDAYS = {
    (1, 1),
    (1, 2),
    (1, 3),
    (1, 4),
    (1, 5),
    (1, 6),
    (1, 7),
    (1, 8),
    (2, 23),
    (3, 8),
    (5, 1),
    (5, 9),
    (6, 12),
    (11, 4),
}

CALENDAR_STATUS_FILTERS = [
    {"key": "created", "label": "создана", "css_class": "calendar-request-created"},
    {"key": "supply", "label": "ожидает снабжения", "css_class": "calendar-request-supply"},
    {"key": "shipment", "label": "ожидает отгрузки", "css_class": "calendar-request-shipment"},
    {"key": "delivery", "label": "ожидает доставку", "css_class": "calendar-request-delivery"},
    {"key": "done", "label": "доставлена", "css_class": "calendar-request-done"},
    {"key": "problem", "label": "с ошибкой", "css_class": "calendar-request-problem"},
]
CALENDAR_STATUS_FILTER_KEYS = [item["key"] for item in CALENDAR_STATUS_FILTERS]
CALENDAR_STATUS_FILTER_CLASSES = {item["key"]: item["css_class"] for item in CALENDAR_STATUS_FILTERS}


def _editable_fields_for_user(user, request_obj):
    role = get_user_role(user)
    if role in {ROLE_ADMIN}:
        return ALL_EDIT_FIELDS
    if role == ROLE_MANAGER:
        return set()
    if role == ROLE_OPERATOR:
        return OPERATOR_EDIT_FIELDS
    if role == ROLE_SUPPLY:
        return SUPPLY_EDIT_FIELDS
    if role == ROLE_TRANSPORT:
        return TRANSPORT_EDIT_FIELDS
    if role == ROLE_WAREHOUSE:
        return WAREHOUSE_EDIT_FIELDS
    if role == ROLE_DRIVER and request_obj.assigned_driver and request_obj.assigned_driver.user_id == user.id:
        return DRIVER_EDIT_FIELDS
    return set()


def _status_choices_for_user(user, request_obj, editable_fields):
    current_status = request_obj.status
    status_labels = dict(STATUS_CHOICES)
    if "status" not in editable_fields:
        return [(current_status, status_labels.get(current_status, current_status))]

    allowed_statuses = set(get_allowed_next_statuses(request_obj))
    role = get_user_role(user)
    if role != ROLE_ADMIN:
        allowed_statuses &= ROLE_STATUS_TARGETS.get(role, set())

    choices = [current_status, *sorted(allowed_statuses)]
    return [(status, status_labels.get(status, status)) for status in choices]


def _configure_role_form_labels(form, user):
    role = get_user_role(user)
    if role == ROLE_SUPPLY and "status_comment" in form.fields:
        form.fields["status_comment"].label = "Комментарий снабжения"
        form.fields["status_comment"].help_text = "Комментарий сохранится в истории статусов при смене статуса заявки."
    elif role == ROLE_TRANSPORT:
        if "assigned_vehicle" in form.fields:
            form.fields["assigned_vehicle"].label = "Назначить машину"
        if "assigned_driver" in form.fields:
            form.fields["assigned_driver"].label = "Назначить водителя"
        if "actual_ship_date" in form.fields:
            form.fields["actual_ship_date"].label = "Дата отправки"
        if "status_comment" in form.fields:
            form.fields["status_comment"].label = "Комментарий транспортного отдела"
            form.fields["status_comment"].help_text = "Комментарий сохранится в истории статусов при смене статуса заявки."
    elif role == ROLE_WAREHOUSE:
        if "warehouse_arrival_date" in form.fields:
            form.fields["warehouse_arrival_date"].label = "Дата поступления на склад"
        if "cz_checked" in form.fields:
            form.fields["cz_checked"].label = "Проверка ЧЗ выполнена"
        if "cz_status" in form.fields:
            form.fields["cz_status"].label = "Статус проверки ЧЗ"
        if "cz_problem" in form.fields:
            form.fields["cz_problem"].label = "Есть проблема ЧЗ"
        if "actual_ship_date" in form.fields:
            form.fields["actual_ship_date"].label = "Дата физической отгрузки"
        if "status_comment" in form.fields:
            form.fields["status_comment"].label = "Комментарий склада"
            form.fields["status_comment"].help_text = "Комментарий сохранится в истории статусов при смене статуса заявки."
    elif role == ROLE_DRIVER:
        if "status" in form.fields:
            form.fields["status"].label = "Статус доставки"
        if "actual_delivery_date" in form.fields:
            form.fields["actual_delivery_date"].label = "Дата доставки"
        if "status_comment" in form.fields:
            form.fields["status_comment"].label = "Комментарий водителя"
            form.fields["status_comment"].help_text = "Комментарий сохранится в истории статусов при смене статуса заявки."
    return form


def _request_timeline(request_obj):
    today = timezone.localdate()
    shipment_overdue = bool(request_obj.planned_ship_date and request_obj.planned_ship_date < today and not request_obj.actual_ship_date)
    delivery_overdue = bool(request_obj.planned_delivery_date and request_obj.planned_delivery_date < today and not request_obj.actual_delivery_date)
    warehouse_overdue = bool(request_obj.supply_eta_date and request_obj.supply_eta_date < today and not request_obj.warehouse_arrival_date)

    return [
        {
            "title": "Поступление на склад",
            "date": request_obj.warehouse_arrival_date,
            "control_date": request_obj.supply_eta_date,
            "control_label": "Ориентир",
            "completed": bool(request_obj.warehouse_arrival_date),
            "overdue": warehouse_overdue,
        },
        {
            "title": "Плановая дата отправки",
            "date": request_obj.planned_ship_date,
            "completed": bool(request_obj.actual_ship_date),
            "overdue": shipment_overdue,
        },
        {
            "title": "Фактическая дата отправки",
            "date": request_obj.actual_ship_date,
            "control_date": request_obj.planned_ship_date,
            "control_label": "План",
            "completed": bool(request_obj.actual_ship_date),
            "overdue": shipment_overdue,
        },
        {
            "title": "Плановая дата доставки",
            "date": request_obj.planned_delivery_date,
            "completed": bool(request_obj.actual_delivery_date or request_obj.status in {STATUS_DELIVERED, STATUS_CLOSED, STATUS_CANCELLED}),
            "overdue": delivery_overdue,
        },
        {
            "title": "Фактическая дата доставки",
            "date": request_obj.actual_delivery_date,
            "control_date": request_obj.planned_delivery_date,
            "control_label": "План",
            "completed": bool(request_obj.actual_delivery_date),
            "overdue": delivery_overdue,
        },
    ]


def _problem_close_statuses(request_obj):
    return sorted(get_allowed_next_statuses(request_obj))


def _problem_close_status_choices(request_obj):
    status_labels = dict(STATUS_CHOICES)
    return [(status, status_labels.get(status, status)) for status in _problem_close_statuses(request_obj)]


def _request_detail_context(request_obj, attachment_form=None, problem_form=None):
    return {
        "request_obj": request_obj,
        "attachment_form": attachment_form or AttachmentForm(),
        "problem_form": problem_form or ProblemReportForm(),
        "close_problem_statuses": _problem_close_statuses(request_obj),
        "close_problem_status_choices": _problem_close_status_choices(request_obj),
        "timeline": _request_timeline(request_obj),
        "drivers": Driver.objects.filter(is_active=True).order_by("full_name"),
        "vehicles": Vehicle.objects.filter(is_active=True).order_by("plate_number"),
        "warehouse_statuses": [
            (status, label)
            for status, label in STATUS_CHOICES
            if status in {STATUS_IN_WAREHOUSE, STATUS_CZ_CHECK, STATUS_READY_TO_SHIP, STATUS_SHIPPED}
        ],
    }


@login_required
@role_required(ROLE_ADMIN, ROLE_OPERATOR)
def client_list(request):
    query = request.GET.get("q", "")
    clients = Client.objects.order_by("name")
    if query:
        clients = clients.filter(
            Q(name__icontains=query)
            | Q(region__icontains=query)
            | Q(contact_name__icontains=query)
            | Q(phone__icontains=query)
            | Q(email__icontains=query)
        )
    return render(request, "logistics/client_list.html", {"clients": clients, "query": query})


@login_required
@role_required(ROLE_ADMIN, ROLE_OPERATOR)
def client_create(request):
    if request.method == "POST":
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save()
            messages.success(request, "Клиент добавлен.")
            return redirect("client_edit", pk=client.pk)
    else:
        form = ClientForm()
    return render(request, "logistics/client_form.html", {"form": form, "title": "Новый клиент"})


@login_required
@role_required(ROLE_ADMIN, ROLE_OPERATOR)
def client_edit(request, pk):
    client = get_object_or_404(Client, pk=pk)
    if request.method == "POST":
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            messages.success(request, "Клиент обновлён.")
            return redirect("client_list")
    else:
        form = ClientForm(instance=client)
    return render(request, "logistics/client_form.html", {"form": form, "client_obj": client, "title": client.name})


@login_required
@role_required(ROLE_ADMIN, ROLE_OPERATOR)
def client_delete(request, pk):
    client = get_object_or_404(Client, pk=pk)
    if request.method == "POST":
        client_name = client.name
        client.delete()
        messages.success(request, f"Клиент «{client_name}» удалён.")
        return redirect("client_list")
    return render(request, "logistics/client_confirm_delete.html", {"client_obj": client})


@login_required
@role_required(ROLE_ADMIN, ROLE_MANAGER, ROLE_OPERATOR, ROLE_SUPPLY, ROLE_TRANSPORT, ROLE_WAREHOUSE, ROLE_DRIVER)
def request_list(request):
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)
    open_problem_qs = ProblemReport.objects.filter(
        request=OuterRef("pk"),
        status__in=[ProblemReport.OPEN, ProblemReport.IN_PROGRESS],
    )
    requests = (
        LogisticsRequest.objects.select_related("warehouse", "assigned_driver", "assigned_vehicle")
        .prefetch_related("problems")
        .annotate(has_open_problem=Exists(open_problem_qs))
        .filter(is_archived=False)
    )
    if get_user_role(request.user) == ROLE_DRIVER:
        requests = requests.filter(assigned_driver__user=request.user)

    quick = request.GET.get("quick", "all")
    status = request.GET.get("status", "")
    client = request.GET.get("client", "")
    region = request.GET.get("region", "")
    warehouse = request.GET.get("warehouse", "")
    driver = request.GET.get("driver", "")
    priority = request.GET.get("priority", "")
    cz_required = request.GET.get("cz_required", "")
    cz_checked = request.GET.get("cz_checked", "")
    has_problem = request.GET.get("has_problem", request.GET.get("problems", ""))
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    query = request.GET.get("q", "")

    if quick == "today":
        requests = requests.filter(Q(planned_ship_date=today) | Q(planned_delivery_date=today))
    elif quick == "tomorrow":
        requests = requests.filter(Q(planned_ship_date=tomorrow) | Q(planned_delivery_date=tomorrow))
    elif quick == "overdue":
        requests = requests.filter(planned_delivery_date__lt=today).exclude(status__in=[STATUS_DELIVERED, STATUS_CLOSED, STATUS_CANCELLED])
    elif quick == "problems":
        requests = requests.filter(Q(has_open_problem=True) | Q(status=STATUS_PROBLEM))
    elif quick == "without_transport":
        requests = requests.filter(Q(assigned_vehicle__isnull=True) | Q(assigned_driver__isnull=True)).exclude(status__in=[STATUS_DELIVERED, STATUS_CLOSED, STATUS_CANCELLED])
    elif quick == "waiting_warehouse":
        requests = requests.filter(status=STATUS_WAITING_ARRIVAL)
    elif quick == "in_transit":
        requests = requests.filter(status=STATUS_IN_TRANSIT)
    elif quick == "delivered":
        requests = requests.filter(status=STATUS_DELIVERED)

    if status:
        requests = requests.filter(status=status)
    if client:
        requests = requests.filter(client_name=client)
    if region:
        requests = requests.filter(region__icontains=region)
    if warehouse.isdigit():
        requests = requests.filter(warehouse_id=warehouse)
    if driver.isdigit():
        requests = requests.filter(assigned_driver_id=driver)
    if priority:
        requests = requests.filter(priority=priority)
    if cz_required in {"yes", "no"}:
        requests = requests.filter(cz_required=cz_required == "yes")
    if cz_checked in {"yes", "no"}:
        requests = requests.filter(cz_checked=cz_checked == "yes")
    if has_problem in {"yes", "open"}:
        requests = requests.filter(Q(has_open_problem=True) | Q(status=STATUS_PROBLEM))
    elif has_problem == "no":
        requests = requests.filter(has_open_problem=False).exclude(status=STATUS_PROBLEM)
    if date_from:
        requests = requests.filter(updated_at__date__gte=date_from)
    if date_to:
        requests = requests.filter(updated_at__date__lte=date_to)
    if query:
        requests = requests.filter(
            Q(request_number__icontains=query)
            | Q(cargo_description__icontains=query)
            | Q(client_name__icontains=query)
            | Q(client_address__icontains=query)
        )

    client_names = (
        LogisticsRequest.objects.filter(is_archived=False)
        .exclude(client_name="")
        .order_by("client_name")
        .values_list("client_name", flat=True)
        .distinct()
    )

    context = {
        "requests": requests,
        "quick_tabs": [
            ("all", "Все"),
            ("today", "Сегодня"),
            ("tomorrow", "Завтра"),
            ("overdue", "Просрочено"),
            ("problems", "Проблемные"),
            ("without_transport", "Без транспорта"),
            ("waiting_warehouse", "Ожидают склад"),
            ("in_transit", "В пути"),
            ("delivered", "Доставлены"),
        ],
        "statuses": STATUS_CHOICES,
        "priorities": LogisticsRequest.PRIORITY_CHOICES,
        "clients": client_names,
        "warehouses": Warehouse.objects.order_by("name", "region"),
        "drivers": Driver.objects.filter(is_active=True).order_by("full_name"),
        "filters": {
            "status": status,
            "client": client,
            "region": region,
            "warehouse": warehouse,
            "driver": driver,
            "priority": priority,
            "cz_required": cz_required,
            "cz_checked": cz_checked,
            "has_problem": has_problem,
            "date_from": date_from,
            "date_to": date_to,
            "quick": quick,
            "q": query,
        },
    }
    return render(request, "logistics/request_list.html", context)


def _month_from_request(request):
    today = timezone.localdate()
    raw_month = request.GET.get("month", "")
    if raw_month:
        try:
            year, month = [int(part) for part in raw_month.split("-", 1)]
            return date(year, month, 1)
        except (TypeError, ValueError):
            pass
    return date(today.year, today.month, 1)


def _shift_month(month_start, delta):
    month = month_start.month + delta
    year = month_start.year
    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return date(year, month, 1)


def _request_calendar_group(request_obj):
    if request_obj.status == STATUS_PROBLEM or getattr(request_obj, "has_open_problem", False):
        return "problem"
    if request_obj.status in {STATUS_DELIVERED, STATUS_CLOSED, STATUS_CANCELLED}:
        return "done"
    if request_obj.status == STATUS_CREATED:
        return "created"
    if request_obj.status in {STATUS_WAITING_SUPPLY, STATUS_WAITING_ARRIVAL}:
        return "supply"
    if request_obj.status in {
        STATUS_IN_WAREHOUSE,
        STATUS_CZ_CHECK,
        STATUS_READY_TO_SHIP,
        STATUS_TRANSPORT_ASSIGNED,
    }:
        return "shipment"
    if request_obj.status in {STATUS_SHIPPED, STATUS_IN_TRANSIT}:
        return "delivery"
    return "created"


def _request_calendar_class(request_obj, index):
    return CALENDAR_STATUS_FILTER_CLASSES[_request_calendar_group(request_obj)]


def _calendar_status_filters_for_request(request):
    profile = getattr(request.user, "profile", None)
    valid_keys = set(CALENDAR_STATUS_FILTER_KEYS)

    if request.GET.get("calendar_filters_submitted") == "1":
        selected = [key for key in request.GET.getlist("status_group") if key in valid_keys]
        if profile:
            profile.calendar_status_filters = selected
            profile.save(update_fields=["calendar_status_filters"])
        return selected

    selected = getattr(profile, "calendar_status_filters", None) if profile else None
    if selected is None:
        return list(CALENDAR_STATUS_FILTER_KEYS)
    return [key for key in selected if key in valid_keys]


def _calendar_date_for_request(request_obj):
    if request_obj.status in {STATUS_WAITING_SUPPLY, STATUS_WAITING_ARRIVAL}:
        return request_obj.supply_eta_date or request_obj.planned_delivery_date
    if request_obj.status in {
        STATUS_IN_WAREHOUSE,
        STATUS_CZ_CHECK,
        STATUS_READY_TO_SHIP,
        STATUS_TRANSPORT_ASSIGNED,
    }:
        return request_obj.planned_ship_date or request_obj.supply_eta_date or request_obj.planned_delivery_date
    if request_obj.status in {STATUS_SHIPPED, STATUS_IN_TRANSIT, STATUS_DELIVERED}:
        return request_obj.actual_delivery_date or request_obj.planned_delivery_date
    return request_obj.planned_delivery_date or request_obj.planned_ship_date or request_obj.supply_eta_date


@login_required
@role_required(ROLE_ADMIN, ROLE_MANAGER, ROLE_OPERATOR, ROLE_SUPPLY, ROLE_TRANSPORT, ROLE_WAREHOUSE, ROLE_DRIVER)
def request_calendar(request):
    month_start = _month_from_request(request)
    month_end = date(month_start.year, month_start.month, calendar_module.monthrange(month_start.year, month_start.month)[1])
    today = timezone.localdate()
    active_status_filters = _calendar_status_filters_for_request(request)
    active_status_filter_set = set(active_status_filters)
    calendar_filters = [
        {
            **item,
            "checked": item["key"] in active_status_filter_set,
        }
        for item in CALENDAR_STATUS_FILTERS
    ]

    open_problem_qs = ProblemReport.objects.filter(
        request=OuterRef("pk"),
        status__in=[ProblemReport.OPEN, ProblemReport.IN_PROGRESS],
    )
    requests = (
        LogisticsRequest.objects.select_related("assigned_driver")
        .annotate(has_open_problem=Exists(open_problem_qs))
        .filter(is_archived=False)
    )
    if get_user_role(request.user) == ROLE_DRIVER:
        requests = requests.filter(assigned_driver__user=request.user)

    dated_requests = requests.filter(
        Q(planned_delivery_date__range=(month_start, month_end))
        | Q(planned_ship_date__range=(month_start, month_end))
        | Q(supply_eta_date__range=(month_start, month_end))
        | Q(actual_delivery_date__range=(month_start, month_end))
    ).order_by(
        "priority",
        "client_name",
    )
    requests_by_date = {}
    for request_obj in dated_requests:
        calendar_group = _request_calendar_group(request_obj)
        if calendar_group not in active_status_filter_set:
            continue
        calendar_date = _calendar_date_for_request(request_obj)
        if not calendar_date or calendar_date < month_start or calendar_date > month_end:
            continue
        day_items = requests_by_date.setdefault(calendar_date, [])
        request_obj.calendar_class = CALENDAR_STATUS_FILTER_CLASSES[calendar_group]
        day_items.append(request_obj)

    weeks = []
    for week in calendar_module.Calendar(firstweekday=0).monthdatescalendar(month_start.year, month_start.month):
        days = []
        for day in week:
            days.append(
                {
                    "date": day,
                    "number": day.day,
                    "in_month": day.month == month_start.month,
                    "is_today": day == today,
                    "is_weekend": day.weekday() >= 5,
                    "is_holiday": (day.month, day.day) in FIXED_HOLIDAYS,
                    "requests": requests_by_date.get(day, []),
                }
            )
        weeks.append(days)

    undated_requests = []
    undated_candidates = requests.filter(
        planned_delivery_date__isnull=True,
        planned_ship_date__isnull=True,
        supply_eta_date__isnull=True,
        actual_delivery_date__isnull=True,
    ).order_by("-updated_at")[:50]
    for request_obj in undated_candidates:
        calendar_group = _request_calendar_group(request_obj)
        if calendar_group not in active_status_filter_set:
            continue
        request_obj.calendar_class = CALENDAR_STATUS_FILTER_CLASSES[calendar_group]
        undated_requests.append(request_obj)
        if len(undated_requests) >= 20:
            break

    return render(
        request,
        "logistics/request_calendar.html",
        {
            "weeks": weeks,
            "month_title": f"{MONTH_NAMES[month_start.month]} {month_start.year}",
            "current_month": month_start.strftime("%Y-%m"),
            "prev_month": _shift_month(month_start, -1).strftime("%Y-%m"),
            "next_month": _shift_month(month_start, 1).strftime("%Y-%m"),
            "undated_requests": undated_requests,
            "weekdays": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
            "calendar_filters": calendar_filters,
        },
    )


@login_required
@role_required(ROLE_ADMIN, ROLE_MANAGER, ROLE_OPERATOR, ROLE_SUPPLY, ROLE_TRANSPORT, ROLE_WAREHOUSE, ROLE_DRIVER)
def request_detail(request, pk):
    request_obj = get_object_or_404(
        LogisticsRequest.objects.select_related("warehouse", "assigned_driver", "assigned_vehicle", "created_by"),
        pk=pk,
    )
    if get_user_role(request.user) == ROLE_DRIVER and (
        not request_obj.assigned_driver or request_obj.assigned_driver.user_id != request.user.id
    ):
        raise PermissionDenied

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "driver_delivered":
            if get_user_role(request.user) != ROLE_DRIVER or not request_obj.assigned_driver or request_obj.assigned_driver.user_id != request.user.id:
                raise PermissionDenied
            if request_obj.status != STATUS_DELIVERED:
                old_status = request_obj.status
                request_obj.status = STATUS_DELIVERED
                request_obj.actual_delivery_date = timezone.localdate()
                request_obj.save(update_fields=["status", "actual_delivery_date", "updated_at"])
                RequestStatusHistory.objects.create(
                    request=request_obj,
                    old_status=old_status,
                    new_status=STATUS_DELIVERED,
                    changed_by=request.user,
                    comment="Доставка отмечена водителем",
                )
                messages.success(request, "Доставка отмечена.")
            return redirect(request_obj)

        if action == "assign_driver":
            if not request.user.is_superuser and get_user_role(request.user) != ROLE_ADMIN:
                raise PermissionDenied
            driver = get_object_or_404(Driver, pk=request.POST.get("assigned_driver"), is_active=True)
            request_obj.assigned_driver = driver
            request_obj.save(update_fields=["assigned_driver", "updated_at"])
            messages.success(request, "Водитель назначен.")
            return redirect(request_obj)

        if action == "supply_date":
            if not request.user.is_superuser and get_user_role(request.user) not in {ROLE_ADMIN, ROLE_SUPPLY}:
                raise PermissionDenied
            supply_eta_date = parse_date(request.POST.get("supply_eta_date") or "")
            if not supply_eta_date:
                messages.error(request, "Укажите дату поступления.")
                return redirect(request_obj)
            request_obj.supply_eta_date = supply_eta_date
            request_obj.save(update_fields=["supply_eta_date", "updated_at"])
            try:
                if request_obj.status == STATUS_CREATED:
                    change_request_status(request_obj, STATUS_WAITING_SUPPLY, request.user, "Заявка принята отделом снабжения")
                if request_obj.status == STATUS_WAITING_SUPPLY:
                    change_request_status(request_obj, STATUS_WAITING_ARRIVAL, request.user, "Снабжение указало дату поставки")
            except ValidationError as exc:
                messages.error(request, exc.message)
                return redirect(request_obj)
            create_role_notification(
                ROLE_WAREHOUSE,
                request_obj,
                f"Ожидается поступление {request_obj.request_number} на {supply_eta_date:%d.%m.%Y}",
            )
            messages.success(request, "Дата поступления обновлена.")
            return redirect(request_obj)

        if action == "supply_cz":
            if not request.user.is_superuser and get_user_role(request.user) not in {ROLE_ADMIN, ROLE_SUPPLY}:
                raise PermissionDenied
            cz_required = request.POST.get("cz_required") == "yes"
            request_obj.cz_required = cz_required
            if not cz_required:
                request_obj.cz_checked = False
                request_obj.cz_problem = False
                request_obj.cz_status = LogisticsRequest.CZ_NOT_REQUIRED
            elif request_obj.cz_status == LogisticsRequest.CZ_NOT_REQUIRED:
                request_obj.cz_status = LogisticsRequest.CZ_PENDING
            request_obj.save(update_fields=["cz_required", "cz_checked", "cz_problem", "cz_status", "updated_at"])
            messages.success(request, "Данные по Честному Знаку обновлены.")
            return redirect(request_obj)

        if action == "assign_transport":
            if not request.user.is_superuser and get_user_role(request.user) not in {ROLE_ADMIN, ROLE_TRANSPORT}:
                raise PermissionDenied
            driver = get_object_or_404(Driver, pk=request.POST.get("assigned_driver"), is_active=True)
            vehicle = get_object_or_404(Vehicle, pk=request.POST.get("assigned_vehicle"), is_active=True)
            planned_ship_date = parse_date(request.POST.get("planned_ship_date") or "")
            request_obj.assigned_driver = driver
            request_obj.assigned_vehicle = vehicle
            update_fields = ["assigned_driver", "assigned_vehicle", "updated_at"]
            if planned_ship_date:
                request_obj.planned_ship_date = planned_ship_date
                update_fields.append("planned_ship_date")
            request_obj.save(update_fields=update_fields)
            messages.success(request, "Водитель и машина назначены.")
            return redirect(request_obj)

        if action == "warehouse_status":
            if not request.user.is_superuser and get_user_role(request.user) not in {ROLE_ADMIN, ROLE_WAREHOUSE}:
                raise PermissionDenied
            planned_ship_date = parse_date(request.POST.get("planned_ship_date") or "")
            new_status = request.POST.get("new_status")
            if new_status not in {STATUS_IN_WAREHOUSE, STATUS_CZ_CHECK, STATUS_READY_TO_SHIP, STATUS_SHIPPED}:
                messages.error(request, "Выберите складской статус.")
                return redirect(request_obj)
            try:
                change_request_status(request_obj, new_status, request.user, "Статус изменён складом")
            except ValidationError as exc:
                messages.error(request, exc.message)
                return redirect(request_obj)
            if planned_ship_date:
                request_obj.planned_ship_date = planned_ship_date
                request_obj.save(update_fields=["planned_ship_date", "updated_at"])
                create_role_notification(
                    ROLE_TRANSPORT,
                    request_obj,
                    f"Склад запланировал отгрузку {request_obj.request_number} на {planned_ship_date:%d.%m.%Y}",
                )
            messages.success(request, "Складской статус обновлён.")
            return redirect(request_obj)

        if action == "attachment":
            attachment_form = AttachmentForm(request.POST, request.FILES)
            if attachment_form.is_valid():
                attachment = attachment_form.save(commit=False)
                attachment.request = request_obj
                attachment.uploaded_by = request.user
                attachment.save()
                messages.success(request, "Вложение добавлено.")
                return redirect(request_obj)
            return render(request, "logistics/request_detail.html", _request_detail_context(request_obj, attachment_form=attachment_form))

        if action == "problem":
            if not can_create_problem(request.user, request_obj):
                raise PermissionDenied

            problem_form = ProblemReportForm(request.POST, request.FILES)
            if problem_form.is_valid():
                try:
                    with transaction.atomic():
                        problem = problem_form.save(commit=False)
                        problem.request = request_obj
                        problem.created_by = request.user
                        problem.save()

                        evidence_file = problem_form.cleaned_data.get("evidence_file")
                        if evidence_file:
                            extension = evidence_file.name.rsplit(".", 1)[-1].lower()
                            file_type = Attachment.PDF_DOCUMENT if extension == "pdf" else Attachment.DAMAGE_PHOTO
                            Attachment.objects.create(
                                request=request_obj,
                                file=evidence_file,
                                file_type=file_type,
                                description=f"Файл к проблеме: {problem.get_problem_type_display()}",
                                uploaded_by=request.user,
                            )

                        change_request_status(request_obj, STATUS_PROBLEM, request.user, "Зарегистрирована проблема")
                except ValidationError as exc:
                    problem_form.add_error(None, exc)
                    return render(request, "logistics/request_detail.html", _request_detail_context(request_obj, problem_form=problem_form))

                messages.success(request, "Проблема зарегистрирована.")
                return redirect(request_obj)
            return render(request, "logistics/request_detail.html", _request_detail_context(request_obj, problem_form=problem_form))

        if action == "close_problem":
            if not can_create_problem(request.user, request_obj):
                raise PermissionDenied
            if request_obj.status != STATUS_PROBLEM:
                messages.error(request, "Закрыть проблему можно только для заявки в статусе «Проблема».")
                return redirect(request_obj)

            problem = get_object_or_404(ProblemReport, pk=request.POST.get("problem_id"), request=request_obj)
            if problem.status == ProblemReport.RESOLVED:
                messages.info(request, "Проблема уже закрыта.")
                return redirect(request_obj)

            close_form = CloseProblemForm(request.POST, allowed_statuses=_problem_close_statuses(request_obj))
            if close_form.is_valid():
                try:
                    with transaction.atomic():
                        problem.status = ProblemReport.RESOLVED
                        problem.resolved_at = timezone.now()
                        problem.resolution_comment = close_form.cleaned_data["resolution_comment"]
                        problem.save(update_fields=["status", "resolved_at", "resolution_comment"])
                        change_request_status(
                            request_obj,
                            close_form.cleaned_data["new_status"],
                            request.user,
                            f"Проблема закрыта: {problem.resolution_comment}",
                        )
                except ValidationError as exc:
                    messages.error(request, exc.message)
                    return redirect(request_obj)

                messages.success(request, "Проблема закрыта.")
                return redirect(request_obj)

            messages.error(request, "Проверьте поля закрытия проблемы.")
            return redirect(request_obj)

    return render(request, "logistics/request_detail.html", _request_detail_context(request_obj))


@login_required
@role_required(ROLE_ADMIN, ROLE_MANAGER, ROLE_OPERATOR)
def request_create(request):
    role = get_user_role(request.user)
    if request.method == "POST":
        form = LogisticsRequestCreateForm(request.POST, user_role=role)
        if form.is_valid():
            request_obj = form.save(commit=False)
            if not request_obj.warehouse_id:
                default_warehouse = Warehouse.objects.order_by("name").first()
                if not default_warehouse:
                    form.add_error(None, "Добавьте хотя бы один склад перед созданием заявки.")
                    return render(request, "logistics/request_form.html", {"form": form, "title": "Создание заявки"})
                request_obj.warehouse = default_warehouse
            skip_supply = form.cleaned_data.get("skip_supply_to_warehouse")
            request_obj.status = STATUS_IN_WAREHOUSE if skip_supply else STATUS_WAITING_SUPPLY
            if skip_supply and not request_obj.warehouse_arrival_date:
                request_obj.warehouse_arrival_date = timezone.localdate()
            request_obj.created_by = request.user
            request_obj.save()
            RequestStatusHistory.objects.create(
                request=request_obj,
                old_status="",
                new_status=request_obj.status,
                changed_by=request.user,
                comment="Заявка создана. Товар уже на складе." if skip_supply else "Заявка создана. Передано в отдел снабжения.",
            )
            create_role_notification(
                ROLE_WAREHOUSE if skip_supply else ROLE_SUPPLY,
                request_obj,
                f"Новая заявка {request_obj.request_number}: {request_obj.client_name}",
            )
            messages.success(request, "Заявка создана.")
            return redirect(request_obj)
    else:
        initial = {}
        planned_delivery_date = parse_date(request.GET.get("planned_delivery_date") or "")
        if planned_delivery_date:
            initial["planned_delivery_date"] = planned_delivery_date
        form = LogisticsRequestCreateForm(initial=initial, user_role=role)

    return render(request, "logistics/request_form.html", {"form": form, "title": "Создание заявки"})


@login_required
@role_required(ROLE_ADMIN, ROLE_MANAGER, ROLE_OPERATOR, ROLE_SUPPLY, ROLE_TRANSPORT, ROLE_WAREHOUSE, ROLE_DRIVER)
def request_edit(request, pk):
    request_obj = get_object_or_404(LogisticsRequest, pk=pk)
    if request_obj.status in COMPLETED_STATUSES and not request.user.is_superuser and get_user_role(request.user) != ROLE_ADMIN:
        raise PermissionDenied
    if not can_edit_request(request.user, request_obj):
        raise PermissionDenied
    editable_fields = _editable_fields_for_user(request.user, request_obj)
    if not editable_fields:
        raise PermissionDenied

    old_status = request_obj.status
    status_choices = _status_choices_for_user(request.user, request_obj, editable_fields)
    user_can_assign_transport = {"assigned_vehicle", "assigned_driver"}.issubset(editable_fields)

    if request.method == "POST":
        old_vehicle_id = request_obj.assigned_vehicle_id
        old_driver_id = request_obj.assigned_driver_id
        form = LogisticsRequestForm(
            request.POST,
            instance=request_obj,
            can_assign_transport=user_can_assign_transport,
            editable_fields=editable_fields,
            status_choices=status_choices,
        )
        _configure_role_form_labels(form, request.user)
        if form.is_valid():
            if set(form.changed_data) - editable_fields:
                raise PermissionDenied

            new_status = form.cleaned_data.get("status", old_status)
            if old_status != new_status and "status" not in editable_fields:
                raise PermissionDenied
            if old_status != new_status and new_status not in dict(status_choices):
                raise PermissionDenied
            if old_status != new_status and not can_change_status(request.user, request_obj, new_status):
                raise PermissionDenied
            new_vehicle_id = old_vehicle_id
            new_driver_id = old_driver_id
            if "assigned_vehicle" in form.fields:
                new_vehicle = form.cleaned_data.get("assigned_vehicle")
                new_vehicle_id = new_vehicle.id if new_vehicle else None
            if "assigned_driver" in form.fields:
                new_driver = form.cleaned_data.get("assigned_driver")
                new_driver_id = new_driver.id if new_driver else None
            if (old_vehicle_id != new_vehicle_id or old_driver_id != new_driver_id) and not user_can_assign_transport:
                raise PermissionDenied

            updated = form.save(commit=False)
            updated.status = old_status
            updated.save()
            if old_status != new_status:
                try:
                    change_request_status(updated, new_status, request.user, form.cleaned_data.get("status_comment"))
                except ValidationError as exc:
                    form.add_error("status", exc)
                    return render(request, "logistics/request_form.html", {"form": form, "request_obj": request_obj, "title": f"Редактирование {request_obj.request_number}"})

            messages.success(request, "Заявка обновлена.")
            return redirect(updated)
    else:
        form = LogisticsRequestForm(
            instance=request_obj,
            can_assign_transport=user_can_assign_transport,
            editable_fields=editable_fields,
            status_choices=status_choices,
        )
        _configure_role_form_labels(form, request.user)

    return render(request, "logistics/request_form.html", {"form": form, "request_obj": request_obj, "title": f"Редактирование {request_obj.request_number}"})
