import calendar as calendar_module
import re
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Case, Exists, IntegerField, OuterRef, Q, Value, When
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme

from apps.accounts.constants import ROLE_ADMIN, ROLE_DRIVER, ROLE_MANAGER, ROLE_OPERATOR, ROLE_SUPPLY, ROLE_TRANSPORT, ROLE_VIEWER, ROLE_WAREHOUSE
from apps.accounts.models import (
    REQUEST_LIST_PERIOD_CHOICES,
    REQUEST_LIST_PERIOD_DAY,
    REQUEST_LIST_PERIOD_MONTH,
    REQUEST_LIST_PERIOD_TWO_WEEKS,
    REQUEST_LIST_PERIOD_WEEK,
)
from apps.accounts.permissions import can_change_status, can_create_problem, can_edit_request, get_user_role, role_required
from apps.documents.forms import AttachmentForm
from apps.documents.models import Attachment
from apps.notifications.models import Notification
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
from .forms import ClientForm, LogisticsRequestCreateForm, LogisticsRequestForm, SupplierForm, SupplyPickupAssignForm, SupplyPickupRequestForm
from .models import CargoItem, Client, LogisticsRequest, RequestStatusHistory, Supplier, SupplyPickupRequest, Warehouse
from .services import change_request_status, get_allowed_next_statuses

User = get_user_model()

ALL_EDIT_FIELDS = set(LogisticsRequestForm.Meta.fields) | {"status_comment"}

OPERATOR_EDIT_FIELDS = {
    "client",
    "client_address",
    "client_contact",
    "client_phone",
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
COMPLETED_STATUS_ORDER_VALUES = [STATUS_DELIVERED, STATUS_CLOSED, STATUS_CANCELLED]

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
    {"key": "supply", "label": "ожидает снабжения", "css_class": "calendar-request-supply"},
    {"key": "shipment", "label": "ожидает отгрузки", "css_class": "calendar-request-shipment"},
    {"key": "delivery", "label": "ожидает доставку", "css_class": "calendar-request-delivery"},
    {"key": "done", "label": "доставлена", "css_class": "calendar-request-done"},
    {"key": "problem", "label": "с ошибкой", "css_class": "calendar-request-problem"},
]
CALENDAR_STATUS_FILTER_KEYS = [item["key"] for item in CALENDAR_STATUS_FILTERS]
CALENDAR_STATUS_FILTER_CLASSES = {item["key"]: item["css_class"] for item in CALENDAR_STATUS_FILTERS}
REQUEST_LIST_PERIOD_KEYS = {key for key, _label in REQUEST_LIST_PERIOD_CHOICES}


class CalendarEntry:
    """Тонкая обёртка над LogisticsRequest для отображения в календаре.
    Позволяет одной заявке появляться несколько раз с разными цветами и подписями."""

    __slots__ = ("_req", "calendar_class", "subtitle")

    def __init__(self, req, calendar_class, subtitle=""):
        self._req = req
        self.calendar_class = calendar_class
        self.subtitle = subtitle

    def get_absolute_url(self):
        return self._req.get_absolute_url()

    @property
    def client_name(self):
        return self._req.client_name

    @property
    def request_number(self):
        return self._req.request_number


class PickupCalendarEntry:
    """Обёртка над SupplyPickupRequest для отображения в транспортном календаре."""

    __slots__ = ("_pickup", "calendar_class", "subtitle")

    def __init__(self, pickup, calendar_class, subtitle=""):
        self._pickup = pickup
        self.calendar_class = calendar_class
        self.subtitle = subtitle

    def get_absolute_url(self):
        return self._pickup.get_absolute_url()

    @property
    def client_name(self):
        return str(self._pickup.supplier)

    @property
    def request_number(self):
        return self._pickup.request_number


# ── Status-group → LogisticsRequest statuses mapping (shared with list view) ──
_LIST_GROUP_TO_STATUSES = {
    "supply":   [STATUS_CREATED, STATUS_WAITING_SUPPLY, STATUS_WAITING_ARRIVAL],
    "shipment": [STATUS_IN_WAREHOUSE, STATUS_CZ_CHECK, STATUS_READY_TO_SHIP, STATUS_TRANSPORT_ASSIGNED],
    "delivery": [STATUS_SHIPPED, STATUS_IN_TRANSIT],
    "done":     [STATUS_DELIVERED, STATUS_CLOSED, STATUS_CANCELLED],
    "problem":  [STATUS_PROBLEM],
}


class PickupListItem:
    """Обёртка над SupplyPickupRequest для единого списка заявок."""

    row_type = "pickup"

    _ROW_CSS = {
        SupplyPickupRequest.STATUS_PENDING:            "s-supply",
        SupplyPickupRequest.STATUS_TRANSPORT_ASSIGNED: "s-warehouse",
        SupplyPickupRequest.STATUS_DELIVERED:          "s-done",
    }
    _SC_CSS = {
        SupplyPickupRequest.STATUS_PENDING:            "sc-supply",
        SupplyPickupRequest.STATUS_TRANSPORT_ASSIGNED: "sc-warehouse",
        SupplyPickupRequest.STATUS_DELIVERED:          "sc-done",
    }

    def __init__(self, pickup):
        self._p = pickup
        self.pk = pickup.pk
        self.request_number = pickup.request_number
        self.client_name = str(pickup.supplier)
        self.client_address = pickup.supplier.region or ""
        self.assigned_driver = pickup.assigned_driver
        self.planned_ship_date = None
        self.planned_delivery_date = pickup.pickup_date
        self.status = pickup.status
        self.updated_at = pickup.updated_at
        self.row_css_class = self._ROW_CSS.get(pickup.status, "s-supply")
        self.status_css_class = self._SC_CSS.get(pickup.status, "sc-supply")

    def get_status_display(self):
        return dict(SupplyPickupRequest.STATUS_CHOICES).get(self.status, self.status)

    def get_absolute_url(self):
        return self._p.get_absolute_url()


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


def _clean_phone_href(phone):
    return re.sub(r"(?!^\+)\D", "", phone or "")


def _phone_from_text(value):
    if not value:
        return ""
    match = re.search(r"\+?\d[\d\s().-]{5,}\d", value)
    return match.group(0).strip() if match else value.strip()


def _driver_contact_phones(request_obj):
    operator_phone = ""
    if request_obj.created_by_id:
        try:
            operator_phone = request_obj.created_by.profile.phone
        except ObjectDoesNotExist:
            operator_phone = ""

    client_phone = ""
    client = Client.objects.filter(name=request_obj.client_name).only("phone").first()
    if client and client.phone:
        client_phone = client.phone
    else:
        client_phone = _phone_from_text(request_obj.client_contact)

    return {
        "operator": {"label": operator_phone, "href": _clean_phone_href(operator_phone)},
        "client": {"label": client_phone, "href": _clean_phone_href(client_phone)},
    }


def _request_list_profile(user):
    try:
        return user.profile
    except ObjectDoesNotExist:
        return None


def _request_list_period_for_user(request):
    profile = _request_list_profile(request.user)
    requested_period = request.GET.get("period", "")
    if requested_period in REQUEST_LIST_PERIOD_KEYS:
        if profile and profile.request_list_period != requested_period:
            profile.request_list_period = requested_period
            profile.save(update_fields=["request_list_period"])
        return requested_period

    saved_period = getattr(profile, "request_list_period", REQUEST_LIST_PERIOD_MONTH) if profile else REQUEST_LIST_PERIOD_MONTH
    return saved_period if saved_period in REQUEST_LIST_PERIOD_KEYS else REQUEST_LIST_PERIOD_MONTH


def _request_list_period_range(period, today):
    if period == REQUEST_LIST_PERIOD_DAY:
        return today, today

    week_start = today - timedelta(days=today.weekday())
    if period == REQUEST_LIST_PERIOD_WEEK:
        return week_start, week_start + timedelta(days=6)
    if period == REQUEST_LIST_PERIOD_TWO_WEEKS:
        return week_start, week_start + timedelta(days=13)

    month_start = date(today.year, today.month, 1)
    month_end = date(today.year, today.month, calendar_module.monthrange(today.year, today.month)[1])
    return month_start, month_end


def _request_list_period_tabs(request, active_period):
    tabs = []
    for key, label in REQUEST_LIST_PERIOD_CHOICES:
        query_params = request.GET.copy()
        query_params["period"] = key
        tabs.append(
            {
                "key": key,
                "label": label,
                "active": key == active_period,
                "query": query_params.urlencode(),
            }
        )
    return tabs


def _default_problem_responsible_user():
    user_model = get_user_model()
    manager = user_model.objects.filter(profile__role=ROLE_MANAGER, is_active=True).order_by("id").first()
    if manager:
        return manager
    admin_user = user_model.objects.filter(profile__role=ROLE_ADMIN, is_active=True).order_by("id").first()
    if admin_user:
        return admin_user
    return user_model.objects.filter(is_superuser=True, is_active=True).order_by("id").first()


def _client_last_addresses():
    latest_addresses = {}
    for item in (
        LogisticsRequest.objects.exclude(client_name="")
        .exclude(client_address="")
        .order_by("client_name", "-updated_at", "-id")
        .values("client_name", "client_address")
    ):
        latest_addresses.setdefault(item["client_name"], item["client_address"])

    return {
        str(client["id"]): latest_addresses.get(client["name"], "")
        for client in Client.objects.order_by("name").values("id", "name")
    }


def _safe_back_url(request, fallback_name="request_list"):
    fallback_url = reverse(fallback_name)
    referer = request.META.get("HTTP_REFERER", "")
    if referer and url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}):
        return referer
    return fallback_url


def _request_detail_context(request_obj, user=None, attachment_form=None, problem_form=None, back_url=None):
    current_viewers = request_obj.viewer_users.all()
    current_viewer_ids = set(current_viewers.values_list("pk", flat=True))
    available_viewers = User.objects.filter(profile__role=ROLE_VIEWER, profile__is_active=True).exclude(pk__in=current_viewer_ids).order_by("last_name", "first_name", "username")
    open_problems = request_obj.problems.filter(status__in=[ProblemReport.OPEN, ProblemReport.IN_PROGRESS]).select_related("responsible_user", "created_by")
    return {
        "request_obj": request_obj,
        "attachment_form": attachment_form or AttachmentForm(),
        "problem_form": problem_form or ProblemReportForm(user=user),
        "close_problem_statuses": _problem_close_statuses(request_obj),
        "close_problem_status_choices": _problem_close_status_choices(request_obj),
        "timeline": _request_timeline(request_obj),
        "driver_contact_phones": _driver_contact_phones(request_obj),
        "drivers": Driver.objects.filter(is_active=True).order_by("full_name"),
        "vehicles": Vehicle.objects.filter(is_active=True).order_by("plate_number"),
        "back_url": back_url or reverse("request_list"),
        "warehouse_statuses": [
            (status, label)
            for status, label in STATUS_CHOICES
            if status in {STATUS_IN_WAREHOUSE, STATUS_CZ_CHECK, STATUS_READY_TO_SHIP, STATUS_SHIPPED}
        ],
        "current_viewers": current_viewers,
        "available_viewers": available_viewers,
        "open_problems": open_problems,
        "cargo_items": request_obj.cargo_items.all(),
        "suppliers": Supplier.objects.order_by("name"),
    }


def _mark_request_notifications_read(user, request_obj):
    role = get_user_role(user)
    if not role:
        return
    Notification.objects.filter(
        recipient_role=role,
        request=request_obj,
        is_read=False,
    ).update(is_read=True)


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
    popup = request.GET.get("popup") == "1" or request.POST.get("popup") == "1"
    if request.method == "POST":
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save()
            if popup:
                return render(request, "logistics/client_popup_done.html", {"client_obj": client})
            messages.success(request, "Клиент добавлен.")
            return redirect("client_edit", pk=client.pk)
    else:
        form = ClientForm()
    return render(request, "logistics/client_form.html", {"form": form, "title": "Новый клиент", "popup": popup})


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


# ── Поставщики ────────────────────────────────────────────────────────────────

@login_required
@role_required(ROLE_ADMIN, ROLE_SUPPLY)
def supplier_list(request):
    query = request.GET.get("q", "")
    suppliers = Supplier.objects.order_by("name")
    if query:
        suppliers = suppliers.filter(
            Q(name__icontains=query)
            | Q(region__icontains=query)
            | Q(contact_name__icontains=query)
            | Q(phone__icontains=query)
            | Q(email__icontains=query)
        )
    return render(request, "logistics/supplier_list.html", {"suppliers": suppliers, "query": query})


@login_required
@role_required(ROLE_ADMIN, ROLE_SUPPLY)
def supplier_create(request):
    if request.method == "POST":
        form = SupplierForm(request.POST)
        if form.is_valid():
            supplier = form.save()
            messages.success(request, "Поставщик добавлен.")
            return redirect("supplier_edit", pk=supplier.pk)
    else:
        form = SupplierForm()
    return render(request, "logistics/supplier_form.html", {"form": form, "title": "Новый поставщик"})


@login_required
@role_required(ROLE_ADMIN, ROLE_SUPPLY)
def supplier_edit(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == "POST":
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            messages.success(request, "Поставщик обновлён.")
            return redirect("supplier_list")
    else:
        form = SupplierForm(instance=supplier)
    return render(request, "logistics/supplier_form.html", {"form": form, "supplier_obj": supplier, "title": supplier.name})


@login_required
@role_required(ROLE_ADMIN, ROLE_SUPPLY)
def supplier_delete(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == "POST":
        supplier_name = supplier.name
        supplier.delete()
        messages.success(request, f"Поставщик «{supplier_name}» удалён.")
        return redirect("supplier_list")
    return render(request, "logistics/supplier_confirm_delete.html", {"supplier_obj": supplier})


# ── Заявки на забор у поставщика ─────────────────────────────────────────────

@login_required
@role_required(ROLE_ADMIN, ROLE_SUPPLY, ROLE_TRANSPORT, ROLE_DRIVER)
def supply_pickup_list(request):
    role = get_user_role(request.user)
    qs = (
        SupplyPickupRequest.objects
        .select_related("supplier", "assigned_vehicle", "assigned_driver", "logistics_request")
        .order_by("-created_at")
    )
    if role == ROLE_DRIVER:
        try:
            from apps.transport.models import Driver
            driver = Driver.objects.get(user=request.user)
            qs = qs.filter(assigned_driver=driver)
        except Exception:
            qs = qs.none()
    status_filter = request.GET.get("status", "")
    if status_filter:
        qs = qs.filter(status=status_filter)
    return render(request, "logistics/supply_pickup_list.html", {
        "pickups": qs,
        "status_filter": status_filter,
        "STATUS_PENDING": SupplyPickupRequest.STATUS_PENDING,
        "STATUS_TRANSPORT_ASSIGNED": SupplyPickupRequest.STATUS_TRANSPORT_ASSIGNED,
        "STATUS_DELIVERED": SupplyPickupRequest.STATUS_DELIVERED,
    })


@login_required
@role_required(ROLE_ADMIN, ROLE_SUPPLY, ROLE_TRANSPORT, ROLE_DRIVER)
def supply_pickup_detail(request, pk):
    pickup = get_object_or_404(
        SupplyPickupRequest.objects.select_related(
            "supplier", "assigned_vehicle", "assigned_driver",
            "logistics_request", "source_cargo_item", "created_by",
        ),
        pk=pk,
    )
    role = get_user_role(request.user)

    # Проверка доступа водителя
    if role == ROLE_DRIVER:
        try:
            from apps.transport.models import Driver
            driver = Driver.objects.get(user=request.user)
            if pickup.assigned_driver_id != driver.pk:
                raise PermissionDenied
        except PermissionDenied:
            raise
        except Exception:
            raise PermissionDenied

    assign_form = SupplyPickupAssignForm(instance=pickup)

    if request.method == "POST":
        action = request.POST.get("action")

        # Назначить транспорт (транспортный отдел)
        if action == "assign_transport":
            if not request.user.is_superuser and role not in {ROLE_ADMIN, ROLE_TRANSPORT}:
                raise PermissionDenied
            assign_form = SupplyPickupAssignForm(request.POST, instance=pickup)
            if assign_form.is_valid():
                assign_form.save()
                if pickup.status == SupplyPickupRequest.STATUS_PENDING:
                    pickup.status = SupplyPickupRequest.STATUS_TRANSPORT_ASSIGNED
                    pickup.save(update_fields=["status", "updated_at"])
                # Уведомить снабжение, склад и водителя
                _notify_pickup_assigned(pickup, request.user)
                messages.success(request, "Транспорт назначен.")
                return redirect(pickup)

        # Водитель — доставлено на склад
        if action == "driver_delivered":
            if role == ROLE_DRIVER:
                try:
                    from apps.transport.models import Driver
                    driver = Driver.objects.get(user=request.user)
                    if pickup.assigned_driver_id != driver.pk:
                        raise PermissionDenied
                except PermissionDenied:
                    raise
                except Exception:
                    raise PermissionDenied
            elif not request.user.is_superuser and role not in {ROLE_ADMIN, ROLE_TRANSPORT}:
                raise PermissionDenied

            odo_raw = request.POST.get("odometer_km", "").strip()
            if not odo_raw:
                messages.error(request, "Введите показания одометра.")
                return redirect(pickup)
            try:
                new_odo = int(odo_raw)
                if new_odo <= 0:
                    raise ValueError
            except ValueError:
                messages.error(request, "Некорректный пробег.")
                return redirect(pickup)

            pickup.odometer_km = new_odo
            pickup.status = SupplyPickupRequest.STATUS_DELIVERED
            pickup.save(update_fields=["odometer_km", "status", "updated_at"])
            # Сохранить пробег в авто
            if pickup.assigned_vehicle_id:
                from apps.transport.models import Vehicle
                Vehicle.objects.filter(pk=pickup.assigned_vehicle_id).update(odometer_km=new_odo)
            _notify_pickup_delivered(pickup, request.user)
            messages.success(request, "Заявка закрыта — товар доставлен на склад.")
            return redirect(pickup)

    return render(request, "logistics/supply_pickup_detail.html", {
        "pickup": pickup,
        "assign_form": assign_form,
        "role": role,
        "STATUS_PENDING": SupplyPickupRequest.STATUS_PENDING,
        "STATUS_TRANSPORT_ASSIGNED": SupplyPickupRequest.STATUS_TRANSPORT_ASSIGNED,
        "STATUS_DELIVERED": SupplyPickupRequest.STATUS_DELIVERED,
    })


@login_required
@role_required(ROLE_ADMIN, ROLE_SUPPLY)
def supply_pickup_create(request):
    """Создание заявки без родительской заявки (standalone)."""
    if request.method == "POST":
        form = SupplyPickupRequestForm(request.POST)
        if form.is_valid():
            pickup = form.save(commit=False)
            pickup.created_by = request.user
            pickup.save()
            create_role_notification(
                ROLE_TRANSPORT,
                None,
                f"Новая заявка на забор {pickup.request_number} у поставщика «{pickup.supplier}» "
                f"на {pickup.pickup_date.strftime('%d.%m.%Y') if pickup.pickup_date else 'дату уточнить'}.",
                pickup_request=pickup,
            )
            messages.success(request, f"Заявка {pickup.request_number} создана.")
            return redirect(pickup)
    else:
        form = SupplyPickupRequestForm()
    return render(request, "logistics/supply_pickup_form.html", {"form": form, "title": "Новая заявка на забор"})


@login_required
@role_required(ROLE_ADMIN, ROLE_SUPPLY)
def supply_pickup_create_for_item(request, req_pk, item_pk):
    """AJAX: создать заявку на забор из позиции товара, вернуть JSON."""
    from django.http import JsonResponse
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    request_obj = get_object_or_404(LogisticsRequest, pk=req_pk)
    item = get_object_or_404(CargoItem, pk=item_pk, request=request_obj)

    form = SupplyPickupRequestForm(request.POST)
    if not form.is_valid():
        errors = {f: e.as_text() for f, e in form.errors.items()}
        return JsonResponse({"ok": False, "errors": errors})

    pickup = form.save(commit=False)
    pickup.logistics_request = request_obj
    pickup.source_cargo_item = item
    pickup.created_by = request.user
    pickup.save()
    create_role_notification(
        ROLE_TRANSPORT,
        None,
        f"Новая заявка на забор {pickup.request_number}: заявка {request_obj.request_number} "
        f"({request_obj.client_name}), поставщик «{pickup.supplier}», "
        f"дата {pickup.pickup_date.strftime('%d.%m.%Y') if pickup.pickup_date else '—'}.",
        pickup_request=pickup,
    )
    return JsonResponse({
        "ok": True,
        "pickup_number": pickup.request_number,
        "pickup_pk": pickup.pk,
        "pickup_url": pickup.get_absolute_url(),
    })


@login_required
@role_required(ROLE_ADMIN, ROLE_SUPPLY)
def supply_pickup_update_date(request, pk):
    """AJAX: изменить дату в уже существующей заявке."""
    from django.http import JsonResponse
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    pickup = get_object_or_404(SupplyPickupRequest, pk=pk)
    new_date = parse_date(request.POST.get("pickup_date") or "") or None
    if not new_date:
        return JsonResponse({"ok": False, "error": "Некорректная дата"})
    old_date = pickup.pickup_date
    pickup.pickup_date = new_date
    pickup.save(update_fields=["pickup_date", "updated_at"])
    if old_date != new_date:
        create_role_notification(
            ROLE_TRANSPORT,
            None,
            f"Заявка на забор {pickup.request_number}: дата изменена с "
            f"{old_date.strftime('%d.%m.%Y') if old_date else '—'} на {new_date.strftime('%d.%m.%Y')}.",
            pickup_request=pickup,
        )
    return JsonResponse({"ok": True, "pickup_date": new_date.strftime("%d.%m.%Y")})


def _notify_pickup_assigned(pickup, user):
    """Уведомить снабжение и склад о назначении транспорта."""
    msg = (
        f"Заявка на забор {pickup.request_number}: назначен "
        f"{pickup.assigned_vehicle or 'авто'} / {pickup.assigned_driver or 'водитель'}, "
        f"дата {pickup.pickup_date.strftime('%d.%m.%Y') if pickup.pickup_date else '—'}."
    )
    create_role_notification(ROLE_SUPPLY, None, msg, pickup_request=pickup)
    create_role_notification(ROLE_WAREHOUSE, None, msg, pickup_request=pickup)


def _notify_pickup_delivered(pickup, user):
    """Уведомить снабжение и склад о доставке товара."""
    msg = (
        f"Заявка на забор {pickup.request_number}: товар доставлен на склад. "
        f"Поставщик: {pickup.supplier}."
    )
    create_role_notification(ROLE_SUPPLY, None, msg, pickup_request=pickup)
    create_role_notification(ROLE_WAREHOUSE, None, msg, pickup_request=pickup)


@login_required
@role_required(ROLE_ADMIN, ROLE_MANAGER, ROLE_OPERATOR, ROLE_SUPPLY, ROLE_TRANSPORT, ROLE_WAREHOUSE, ROLE_DRIVER, ROLE_VIEWER)
def request_list(request):
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)
    active_period = _request_list_period_for_user(request)
    period_start, period_end = _request_list_period_range(active_period, today)
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
    elif get_user_role(request.user) == ROLE_VIEWER:
        requests = requests.filter(viewer_users=request.user)

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

    requests = requests.filter(
        Q(supply_eta_date__range=(period_start, period_end))
        | Q(planned_ship_date__range=(period_start, period_end))
        | Q(planned_delivery_date__range=(period_start, period_end))
        | Q(actual_delivery_date__range=(period_start, period_end))
    )

    # ── Status-group filter (copied from transport calendar) ───────────────────
    _list_filter_submitted = request.GET.get("list_filters_submitted") == "1"
    if _list_filter_submitted:
        active_groups = [k for k in request.GET.getlist("status_group") if k in CALENDAR_STATUS_FILTER_KEYS]
        request.session["list_status_filters"] = active_groups
    else:
        active_groups = request.session.get("list_status_filters", list(CALENDAR_STATUS_FILTER_KEYS))
    active_group_set = set(active_groups)

    if active_group_set != set(CALENDAR_STATUS_FILTER_KEYS):
        allowed_statuses = []
        for gk in active_group_set:
            allowed_statuses.extend(_LIST_GROUP_TO_STATUSES.get(gk, []))
        requests = requests.filter(status__in=allowed_statuses)

    requests = requests.annotate(
        completed_sort=Case(
            When(status__in=COMPLETED_STATUS_ORDER_VALUES, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        )
    ).order_by("completed_sort", "-updated_at", "-id")

    # ── Merge SupplyPickupRequest for supply / transport / admin ───────────────
    user_role = get_user_role(request.user)
    show_pickups = request.user.is_superuser or user_role in {ROLE_ADMIN, ROLE_SUPPLY, ROLE_TRANSPORT}
    pickup_items = []
    if show_pickups:
        pickup_qs = (
            SupplyPickupRequest.objects
            .select_related("supplier", "assigned_driver", "assigned_vehicle")
            .filter(
                Q(pickup_date__range=(period_start, period_end))
                | Q(pickup_date__isnull=True, status__in=[
                    SupplyPickupRequest.STATUS_PENDING,
                    SupplyPickupRequest.STATUS_TRANSPORT_ASSIGNED,
                ])
            )
        )
        if "supply" not in active_group_set:
            pickup_qs = pickup_qs.exclude(status__in=[
                SupplyPickupRequest.STATUS_PENDING,
                SupplyPickupRequest.STATUS_TRANSPORT_ASSIGNED,
            ])
        if "done" not in active_group_set:
            pickup_qs = pickup_qs.exclude(status=SupplyPickupRequest.STATUS_DELIVERED)
        pickup_items = [PickupListItem(p) for p in pickup_qs.order_by("-updated_at")]

    if pickup_items:
        _done_statuses = {STATUS_DELIVERED, STATUS_CLOSED, STATUS_CANCELLED}

        def _sort_key(item):
            is_done = (
                item.status == SupplyPickupRequest.STATUS_DELIVERED
                if getattr(item, "row_type", "request") == "pickup"
                else item.status in _done_statuses
            )
            d = item.planned_delivery_date
            ts = item.updated_at.timestamp() if item.updated_at else 0
            return (1 if is_done else 0, d is None, d or date.min, -ts)

        all_items = sorted(list(requests) + pickup_items, key=_sort_key)
    else:
        all_items = requests

    list_filters = [
        {**f, "checked": f["key"] in active_group_set}
        for f in CALENDAR_STATUS_FILTERS
    ]

    client_names = (
        LogisticsRequest.objects.filter(is_archived=False)
        .exclude(client_name="")
        .order_by("client_name")
        .values_list("client_name", flat=True)
        .distinct()
    )

    context = {
        "requests": all_items,
        "list_filters": list_filters,
        "show_pickups": show_pickups,
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
        "period_tabs": _request_list_period_tabs(request, active_period),
        "active_period": active_period,
        "period_start": period_start,
        "period_end": period_end,
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
    created_date = timezone.localtime(request_obj.created_at).date()
    if request_obj.status == STATUS_CREATED:
        return request_obj.planned_delivery_date or created_date
    if request_obj.status == STATUS_WAITING_SUPPLY:
        return request_obj.planned_delivery_date or request_obj.supply_eta_date or created_date
    if request_obj.status == STATUS_WAITING_ARRIVAL:
        return request_obj.planned_delivery_date or request_obj.planned_ship_date or request_obj.supply_eta_date or created_date
    if request_obj.status in {
        STATUS_IN_WAREHOUSE,
        STATUS_CZ_CHECK,
        STATUS_READY_TO_SHIP,
    }:
        return request_obj.planned_delivery_date or request_obj.planned_ship_date or request_obj.supply_eta_date or created_date
    if request_obj.status == STATUS_TRANSPORT_ASSIGNED:
        return request_obj.planned_delivery_date or request_obj.planned_ship_date or request_obj.actual_ship_date or created_date
    if request_obj.status in {STATUS_SHIPPED, STATUS_IN_TRANSIT}:
        return request_obj.planned_delivery_date or request_obj.actual_ship_date or created_date
    if request_obj.status in {STATUS_DELIVERED, STATUS_CLOSED, STATUS_CANCELLED}:
        return request_obj.actual_delivery_date or request_obj.planned_delivery_date or created_date
    if request_obj.status == STATUS_PROBLEM:
        return (
            request_obj.actual_delivery_date
            or request_obj.actual_ship_date
            or request_obj.planned_delivery_date
            or request_obj.planned_ship_date
            or request_obj.supply_eta_date
            or created_date
        )
    return created_date


@login_required
@role_required(ROLE_ADMIN, ROLE_MANAGER, ROLE_OPERATOR, ROLE_SUPPLY, ROLE_TRANSPORT, ROLE_WAREHOUSE, ROLE_DRIVER, ROLE_VIEWER)
def request_calendar(request):
    month_start = _month_from_request(request)
    month_end = date(month_start.year, month_start.month, calendar_module.monthrange(month_start.year, month_start.month)[1])
    today = timezone.localdate()
    user_role = get_user_role(request.user)
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
    requests_qs = (
        LogisticsRequest.objects.select_related("assigned_driver")
        .annotate(has_open_problem=Exists(open_problem_qs))
        .filter(is_archived=False)
    )
    if user_role == ROLE_DRIVER:
        requests_qs = requests_qs.filter(assigned_driver__user=request.user)
    elif user_role == ROLE_VIEWER:
        requests_qs = requests_qs.filter(viewer_users=request.user)

    # ── Календарь Транспортного отдела ────────────────────────────────────────
    # Работает иначе: один заказ может появляться несколько раз.
    # «Ожидает снабжения» → одна запись на каждую позицию груза с датой поступления.
    # «Ожидает доставку»  → одна запись на заявку по плановой дате доставки.
    if user_role == ROLE_TRANSPORT:
        requests_by_date = {}

        # Supply entries: заявки на забор у поставщика с pickup_date в текущем месяце
        if "supply" in active_status_filter_set:
            _pickup_status_labels = {
                SupplyPickupRequest.STATUS_PENDING: "Новая",
                SupplyPickupRequest.STATUS_TRANSPORT_ASSIGNED: "Транспорт назначен",
            }
            pickup_reqs = (
                SupplyPickupRequest.objects
                .filter(
                    pickup_date__range=(month_start, month_end),
                )
                .exclude(status=SupplyPickupRequest.STATUS_DELIVERED)
                .select_related("supplier")
                .order_by("pickup_date", "request_number")
            )
            for pr in pickup_reqs:
                requests_by_date.setdefault(pr.pickup_date, []).append(
                    PickupCalendarEntry(
                        pr,
                        CALENDAR_STATUS_FILTER_CLASSES["supply"],
                        _pickup_status_labels.get(pr.status, ""),
                    )
                )

        # Delivery entries: по одной на заявку с planned_delivery_date в текущем месяце
        if "delivery" in active_status_filter_set:
            delivery_reqs = (
                requests_qs
                .filter(planned_delivery_date__range=(month_start, month_end))
                .order_by("priority", "client_name")
            )
            for req in delivery_reqs:
                requests_by_date.setdefault(req.planned_delivery_date, []).append(
                    CalendarEntry(req, CALENDAR_STATUS_FILTER_CLASSES["delivery"])
                )

        undated_requests = []

    # ── Стандартный календарь для всех остальных ролей ────────────────────────
    else:
        dated_requests = requests_qs.filter(
            Q(planned_delivery_date__range=(month_start, month_end))
            | Q(planned_ship_date__range=(month_start, month_end))
            | Q(supply_eta_date__range=(month_start, month_end))
            | Q(actual_ship_date__range=(month_start, month_end))
            | Q(actual_delivery_date__range=(month_start, month_end))
            | Q(created_at__date__range=(month_start, month_end))
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

        undated_requests = []
        undated_candidates = requests_qs.filter(
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
@role_required(ROLE_ADMIN, ROLE_MANAGER, ROLE_OPERATOR, ROLE_SUPPLY, ROLE_TRANSPORT, ROLE_WAREHOUSE, ROLE_DRIVER, ROLE_VIEWER)
def request_detail(request, pk):
    request_obj = get_object_or_404(
        LogisticsRequest.objects.select_related("warehouse", "assigned_driver", "assigned_vehicle", "created_by"),
        pk=pk,
    )
    user_role = get_user_role(request.user)
    if user_role == ROLE_DRIVER and (
        not request_obj.assigned_driver or request_obj.assigned_driver.user_id != request.user.id
    ):
        raise PermissionDenied
    if user_role == ROLE_VIEWER and not request_obj.viewer_users.filter(pk=request.user.pk).exists():
        raise PermissionDenied
    _mark_request_notifications_read(request.user, request_obj)

    # Запоминаем откуда пришли (список или календарь) только на GET и только если referer —
    # не сама страница заявки. POST-редиректы внутри страницы не должны перезаписывать back_url.
    session_key = f"back_url_req_{pk}"
    if request.method == "GET":
        referer = request.META.get("HTTP_REFERER", "")
        if referer and url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}):
            if f"/requests/{pk}/" not in referer:
                request.session[session_key] = referer
    back_url = request.session.get(session_key, reverse("request_list"))

    if user_role == ROLE_VIEWER:
        return render(request, "logistics/request_detail.html", _request_detail_context(request_obj, user=request.user, back_url=back_url))

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "add_viewer":
            if not request.user.is_superuser and user_role not in {ROLE_ADMIN, ROLE_OPERATOR}:
                raise PermissionDenied
            viewer_pk = request.POST.get("viewer_user_id")
            if viewer_pk:
                viewer = get_object_or_404(User, pk=viewer_pk, profile__role=ROLE_VIEWER)
                request_obj.viewer_users.add(viewer)
                messages.success(request, "Наблюдатель добавлен.")
            return redirect(request_obj)

        if action == "remove_viewer":
            if not request.user.is_superuser and user_role not in {ROLE_ADMIN, ROLE_OPERATOR}:
                raise PermissionDenied
            viewer_pk = request.POST.get("viewer_user_id")
            if viewer_pk:
                request_obj.viewer_users.remove(viewer_pk)
                messages.success(request, "Наблюдатель удалён.")
            return redirect(request_obj)

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
                create_role_notification(
                    ROLE_TRANSPORT,
                    request_obj,
                    f"Заявка {request_obj.request_number} доставлена водителем.",
                )
                # Сохраняем показания одометра в карточку автомобиля
                odo_raw = request.POST.get("odometer_km", "").strip()
                if odo_raw and request_obj.assigned_vehicle_id:
                    try:
                        new_odo = int(odo_raw)
                        if new_odo > 0:
                            Vehicle.objects.filter(pk=request_obj.assigned_vehicle_id).update(odometer_km=new_odo)
                    except (ValueError, TypeError):
                        pass
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

        if action == "warehouse_receive":
            if not request.user.is_superuser and get_user_role(request.user) not in {ROLE_ADMIN, ROLE_WAREHOUSE}:
                raise PermissionDenied
            if request.POST.get("goods_received") != "on":
                messages.error(request, "Отметьте, что товар принят.")
                return redirect(request_obj)
            if request_obj.cz_required and request.POST.get("cz_checked") != "on":
                messages.error(request, "Подтвердите соответствие Честного Знака.")
                return redirect(request_obj)

            request_obj.warehouse_arrival_date = timezone.localdate()
            update_fields = ["warehouse_arrival_date", "updated_at"]
            if request_obj.cz_required:
                request_obj.cz_checked = True
                request_obj.cz_problem = False
                request_obj.cz_status = LogisticsRequest.CZ_OK
                update_fields += ["cz_checked", "cz_problem", "cz_status"]
            request_obj.save(update_fields=update_fields)
            try:
                if request_obj.status == STATUS_WAITING_ARRIVAL:
                    change_request_status(request_obj, STATUS_IN_WAREHOUSE, request.user, "Склад принял товар")
            except ValidationError as exc:
                messages.error(request, exc.message)
                return redirect(request_obj)
            messages.success(request, "Поступление подтверждено.")
            return redirect(request_obj)

        if action == "warehouse_ship":
            if not request.user.is_superuser and get_user_role(request.user) not in {ROLE_ADMIN, ROLE_WAREHOUSE}:
                raise PermissionDenied
            if request.POST.get("goods_shipped") != "on":
                messages.error(request, "Отметьте, что товар отгружен.")
                return redirect(request_obj)
            request_obj.actual_ship_date = timezone.localdate()
            request_obj.save(update_fields=["actual_ship_date", "updated_at"])
            try:
                if request_obj.status == STATUS_TRANSPORT_ASSIGNED:
                    change_request_status(request_obj, STATUS_SHIPPED, request.user, "Склад подтвердил физическую отгрузку")
            except ValidationError as exc:
                messages.error(request, exc.message)
                return redirect(request_obj)
            messages.success(request, "Отгрузка подтверждена.")
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
            return render(request, "logistics/request_detail.html", _request_detail_context(request_obj, user=request.user, attachment_form=attachment_form, back_url=back_url))

        if action == "problem":
            if not can_create_problem(request.user, request_obj):
                raise PermissionDenied

            problem_form = ProblemReportForm(request.POST, request.FILES, user=request.user)
            if problem_form.is_valid():
                try:
                    with transaction.atomic():
                        problem = problem_form.save(commit=False)
                        problem.request = request_obj
                        problem.created_by = request.user
                        if get_user_role(request.user) == ROLE_DRIVER and not problem.responsible_user_id:
                            problem.responsible_user = _default_problem_responsible_user()
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
                    return render(request, "logistics/request_detail.html", _request_detail_context(request_obj, user=request.user, problem_form=problem_form, back_url=back_url))

                messages.success(request, "Проблема зарегистрирована.")
                return redirect(request_obj)
            return render(request, "logistics/request_detail.html", _request_detail_context(request_obj, user=request.user, problem_form=problem_form, back_url=back_url))

        if action == "resolve_problem":
            if not request.user.is_superuser and user_role not in {ROLE_ADMIN, ROLE_MANAGER, ROLE_OPERATOR, ROLE_SUPPLY, ROLE_TRANSPORT}:
                raise PermissionDenied
            problem = get_object_or_404(ProblemReport, pk=request.POST.get("problem_id"), request=request_obj)
            if problem.status == ProblemReport.RESOLVED:
                messages.info(request, "Проблема уже закрыта.")
                return redirect(request_obj)
            reply = request.POST.get("resolution_reply", "").strip()
            if not reply:
                messages.error(request, "Введите текст ответа.")
                return redirect(request_obj)
            with transaction.atomic():
                problem.status = ProblemReport.RESOLVED
                problem.resolved_at = timezone.now()
                problem.resolution_comment = reply
                problem.save(update_fields=["status", "resolved_at", "resolution_comment"])
                still_open = request_obj.problems.filter(status__in=[ProblemReport.OPEN, ProblemReport.IN_PROGRESS]).exists()
                if not still_open and request_obj.status == STATUS_PROBLEM:
                    prev_status = (
                        request_obj.status_history
                        .exclude(new_status=STATUS_PROBLEM)
                        .order_by("-created_at")
                        .values_list("new_status", flat=True)
                        .first()
                    ) or STATUS_CREATED
                    try:
                        change_request_status(request_obj, prev_status, request.user, f"Проблема решена: {reply}")
                    except ValidationError:
                        pass
            messages.success(request, "Проблема закрыта.")
            return redirect(request_obj)

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

    return render(request, "logistics/request_detail.html", _request_detail_context(request_obj, user=request.user, back_url=back_url))


@login_required
@role_required(ROLE_ADMIN, ROLE_MANAGER, ROLE_OPERATOR)
def request_create_from_pdf(request):
    """Upload a 'Заказ клиента' or 'Счёт-проформа' PDF and open a pre-filled create form."""
    from .pdf_parser import parse_pdf_auto

    if request.method == "GET":
        return render(request, "logistics/request_from_pdf.html")

    uploaded = request.FILES.get("pdf_file")
    if not uploaded:
        messages.error(request, "Выберите PDF-файл.")
        return render(request, "logistics/request_from_pdf.html")
    if not uploaded.name.lower().endswith(".pdf"):
        messages.error(request, "Файл должен быть в формате PDF.")
        return render(request, "logistics/request_from_pdf.html")

    try:
        parsed, _fmt = parse_pdf_auto(uploaded)
    except Exception as exc:
        messages.error(request, f"Не удалось разобрать PDF: {exc}")
        return render(request, "logistics/request_from_pdf.html")

    # ── Build initial dict ────────────────────────────────────────────────
    initial = {}
    if parsed["order_number"]:
        initial["request_number"] = parsed["order_number"]
    if parsed["client_address"]:
        initial["client_address"] = parsed["client_address"]
    if parsed.get("client_contact"):
        initial["client_contact"] = parsed["client_contact"]
    if parsed.get("client_phone"):
        initial["client_phone"] = parsed["client_phone"]
    # cargo_description намеренно не заполняем — оператор вводит сам
    if parsed["cargo_places_count"]:
        initial["cargo_places_count"] = parsed["cargo_places_count"]
    if parsed.get("cargo_weight_kg"):
        initial["cargo_weight_kg"] = parsed["cargo_weight_kg"]
    if parsed["order_date"]:
        initial["planned_delivery_date"] = parsed["order_date"]

    role = get_user_role(request.user)
    form = LogisticsRequestCreateForm(initial=initial, user_role=role, from_pdf=True)

    parse_info = {
        "order_number": parsed["order_number"],
        "order_date": parsed["order_date"],
        "client_name_raw": parsed["client_name_raw"],
        "items": parsed["items"],   # передаём в шаблон для pre-fill таблицы позиций
    }

    available_viewers = User.objects.filter(
        profile__role=ROLE_VIEWER, profile__is_active=True
    ).order_by("last_name", "first_name", "username")

    return render(request, "logistics/request_form.html", {
        "form": form,
        "title": "Создание заявки из файла",
        "client_last_addresses": _client_last_addresses(),
        "form_action": reverse("request_create"),
        "parse_info": parse_info,
        "available_viewers": available_viewers,
    })


@login_required
@role_required(ROLE_ADMIN, ROLE_MANAGER, ROLE_OPERATOR)
def request_create(request):
    role = get_user_role(request.user)
    if request.method == "POST":
        from_pdf = request.POST.get("from_pdf") == "1"
        form = LogisticsRequestCreateForm(request.POST, user_role=role, from_pdf=from_pdf)
        if form.is_valid():
            request_obj = form.save(commit=False)
            # При создании из PDF — берём имя клиента напрямую из текстового поля
            if from_pdf:
                client_name_override = request.POST.get("client_name_override", "").strip()
                if client_name_override:
                    request_obj.client_name = client_name_override
            if not request_obj.warehouse_id:
                default_warehouse = Warehouse.objects.order_by("name").first()
                if not default_warehouse:
                    form.add_error(None, "Добавьте хотя бы один склад перед созданием заявки.")
                    return render(
                        request,
                        "logistics/request_form.html",
                        {
                            "form": form,
                            "title": "Создание заявки",
                            "enable_client_tools": True,
                            "operator_create_layout": role == ROLE_OPERATOR,
                            "client_last_addresses": _client_last_addresses(),
                        },
                    )
                request_obj.warehouse = default_warehouse
            skip_supply = form.cleaned_data.get("skip_supply_to_warehouse")
            request_obj.created_by = request.user
            request_obj.save()  # сохраняем первым — нужен PK для FK CargoItem
            # Наблюдатель (одиночный выбор через viewer_user_id)
            viewer_id = request.POST.get("viewer_user_id", "").strip()
            if viewer_id:
                try:
                    viewer = User.objects.get(pk=viewer_id, profile__role=ROLE_VIEWER)
                    request_obj.viewer_users.add(viewer)
                except (User.DoesNotExist, ValueError):
                    pass

            # ── Сохранить позиции груза из формы ─────────────────────────
            item_names = request.POST.getlist("cargo_item_name")
            item_qtys  = request.POST.getlist("cargo_item_qty")
            supply_idx = set(request.POST.getlist("cargo_supply_idx"))
            for i, iname in enumerate(item_names):
                iname = iname.strip()
                if not iname:
                    continue
                CargoItem.objects.create(
                    request=request_obj,
                    name=iname,
                    qty=item_qtys[i].strip() if i < len(item_qtys) else "",
                    needs_supply=(str(i) in supply_idx),
                    position=i,
                )

            # ── Статус и уведомление ──────────────────────────────────────
            any_needs_supply = request_obj.cargo_items.filter(needs_supply=True).exists()
            skip_supply = skip_supply or (item_names and not any_needs_supply)
            if skip_supply:
                request_obj.status = STATUS_READY_TO_SHIP
                notif_role  = ROLE_WAREHOUSE
                history_msg = "Заявка создана. Все товары на складе, готова к отгрузке."
            else:
                request_obj.status = STATUS_WAITING_SUPPLY
                notif_role  = ROLE_SUPPLY
                history_msg = "Заявка создана. Передано в отдел снабжения."
            request_obj.save(update_fields=["status", "updated_at"])
            RequestStatusHistory.objects.create(
                request=request_obj,
                old_status="",
                new_status=request_obj.status,
                changed_by=request.user,
                comment=history_msg,
            )
            create_role_notification(
                notif_role,
                request_obj,
                f"Новая заявка {request_obj.request_number}: {request_obj.client_name}",
            )
            if request_obj.planned_delivery_date:
                create_role_notification(
                    ROLE_TRANSPORT,
                    request_obj,
                    f"Новая заявка {request_obj.request_number} ({request_obj.client_name}): "
                    f"плановая доставка {request_obj.planned_delivery_date:%d.%m.%Y} — подготовьте автомобиль.",
                )
            messages.success(request, "Заявка создана.")
            return redirect(request_obj)
    else:
        initial = {}
        planned_delivery_date = parse_date(request.GET.get("planned_delivery_date") or "")
        if planned_delivery_date:
            initial["planned_delivery_date"] = planned_delivery_date
        form = LogisticsRequestCreateForm(initial=initial, user_role=role)

    available_viewers = User.objects.filter(
        profile__role=ROLE_VIEWER, profile__is_active=True
    ).order_by("last_name", "first_name", "username")

    return render(
        request,
        "logistics/request_form.html",
        {
            "form": form,
            "title": "Создание заявки",
            "enable_client_tools": True,
            "client_last_addresses": _client_last_addresses(),
            "available_viewers": available_viewers,
        },
    )


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

            # ── Обновить позиции груза (только для admin/operator) ────────
            edit_role = get_user_role(request.user)
            if request.user.is_superuser or edit_role in {ROLE_ADMIN, ROLE_OPERATOR}:
                item_names = request.POST.getlist("cargo_item_name")
                if item_names:  # таблица была отправлена
                    item_qtys  = request.POST.getlist("cargo_item_qty")
                    supply_idx = set(request.POST.getlist("cargo_supply_idx"))
                    # Сохраняем поля снабжения по позиции перед удалением —
                    # чтобы не затереть то, что выставил отдел снабжения
                    supply_fields = {
                        item.position: {
                            "needs_cz": item.needs_cz,
                            "supply_date": item.supply_date,
                        }
                        for item in updated.cargo_items.all()
                    }
                    updated.cargo_items.all().delete()
                    for i, iname in enumerate(item_names):
                        iname = iname.strip()
                        if not iname:
                            continue
                        preserved = supply_fields.get(i, {})
                        CargoItem.objects.create(
                            request=updated,
                            name=iname,
                            qty=item_qtys[i].strip() if i < len(item_qtys) else "",
                            needs_supply=(str(i) in supply_idx),
                            needs_cz=preserved.get("needs_cz", False),
                            supply_date=preserved.get("supply_date", None),
                            position=i,
                        )

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

    inactive_vehicle_ids = list(Vehicle.objects.filter(is_active=False).values_list("pk", flat=True))
    current_viewers = request_obj.viewer_users.all()
    current_viewer_ids = set(current_viewers.values_list("pk", flat=True))
    available_viewers = User.objects.filter(
        profile__role=ROLE_VIEWER, profile__is_active=True
    ).exclude(pk__in=current_viewer_ids).order_by("last_name", "first_name", "username")
    return render(request, "logistics/request_form.html", {
        "form": form,
        "request_obj": request_obj,
        "title": f"Редактирование {request_obj.request_number}",
        "inactive_vehicle_ids": inactive_vehicle_ids,
        "current_viewers": current_viewers,
        "available_viewers": available_viewers,
    })


@login_required
@role_required(ROLE_ADMIN, ROLE_OPERATOR)
def request_delete(request, pk):
    request_obj = get_object_or_404(LogisticsRequest, pk=pk)
    # Оператор не может удалить завершённую заявку
    if request_obj.status in COMPLETED_STATUSES and not request.user.is_superuser and get_user_role(request.user) != ROLE_ADMIN:
        raise PermissionDenied
    if request.method == "POST":
        number = request_obj.request_number
        request_obj.delete()  # CASCADE: уведомления, проблемы, позиции, история — всё удаляется
        messages.success(request, f"Заявка {number} удалена.")
        return redirect("request_list")
    return redirect("request_edit", pk=pk)


# ── Vehicles ──────────────────────────────────────────────────────────────────

@login_required
@role_required(ROLE_ADMIN, ROLE_TRANSPORT)
def vehicle_toggle_active(request, pk):
    from django.http import JsonResponse
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    vehicle = get_object_or_404(Vehicle, pk=pk)
    vehicle.is_active = not vehicle.is_active
    vehicle.save(update_fields=["is_active"])
    return JsonResponse({"is_active": vehicle.is_active})


@login_required
@role_required(ROLE_ADMIN, ROLE_TRANSPORT, ROLE_MANAGER, ROLE_OPERATOR)
def vehicle_list(request):
    vehicles = Vehicle.objects.all().order_by("-is_active", "plate_number")
    active_count   = sum(1 for v in vehicles if v.is_active)
    inactive_count = len(vehicles) - active_count
    can_edit = request.user.is_superuser or get_user_role(request.user) in {ROLE_ADMIN, ROLE_TRANSPORT}
    return render(request, "logistics/vehicles.html", {
        "vehicles": vehicles,
        "can_edit": can_edit,
        "active_count": active_count,
        "inactive_count": inactive_count,
    })


@login_required
@role_required(ROLE_ADMIN, ROLE_TRANSPORT)
def vehicle_edit(request, pk):
    import decimal
    vehicle = get_object_or_404(Vehicle, pk=pk)
    if request.method == "POST":
        vehicle.name = request.POST.get("name", vehicle.name).strip()
        vehicle.vehicle_type = request.POST.get("vehicle_type", vehicle.vehicle_type).strip()
        vehicle.color = request.POST.get("color", vehicle.color).strip()
        vehicle.notes = request.POST.get("notes", vehicle.notes).strip()
        vehicle.is_active = request.POST.get("is_active") == "on"
        year_raw = request.POST.get("year", "").strip()
        mw_raw = request.POST.get("max_weight_kg", "").strip()
        mv_raw = request.POST.get("max_volume_m3", "").strip()
        if mw_raw:
            try:
                vehicle.max_weight_kg = int(mw_raw)
            except (ValueError, TypeError):
                pass
        if mv_raw:
            try:
                vehicle.max_volume_m3 = decimal.Decimal(mv_raw)
            except Exception:
                pass
        else:
            # поле пришло пустым (браузер не отправил валидное число) — не затираем
            pass
        try:
            vehicle.year = int(year_raw) if year_raw else None
        except (ValueError, TypeError):
            vehicle.year = None
        odo_raw = request.POST.get("odometer_km", "").strip()
        svc_raw = request.POST.get("service_due_km", "").strip()
        try:
            vehicle.odometer_km = int(odo_raw) if odo_raw else None
        except (ValueError, TypeError):
            vehicle.odometer_km = None
        try:
            if svc_raw:
                # Пользователь вводит остаток «сколько км до ТО».
                # Сохраняем абсолютную отметку: текущий пробег + введённый интервал.
                svc_remaining = int(svc_raw)
                current_odo = vehicle.odometer_km or 0
                vehicle.service_due_km = current_odo + svc_remaining
            else:
                vehicle.service_due_km = None
        except (ValueError, TypeError):
            vehicle.service_due_km = None
        photo = request.FILES.get("photo")
        if photo:
            vehicle.photo = photo
        vehicle.save()
        messages.success(request, f"Автомобиль {vehicle.plate_number} обновлён.")
        return redirect("vehicle_list")

    return render(request, "logistics/vehicle_edit.html", {"vehicle": vehicle})


# ── Drivers ───────────────────────────────────────────────────────────────────

@login_required
@role_required(ROLE_ADMIN, ROLE_TRANSPORT)
def driver_toggle_active(request, pk):
    from django.http import JsonResponse
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    driver = get_object_or_404(Driver, pk=pk)
    driver.is_active = not driver.is_active
    driver.save(update_fields=["is_active"])
    return JsonResponse({"is_active": driver.is_active})


@login_required
@role_required(ROLE_ADMIN, ROLE_TRANSPORT, ROLE_MANAGER, ROLE_OPERATOR)
def driver_list(request):
    drivers = Driver.objects.all().order_by("-is_active", "full_name")
    active_count   = sum(1 for d in drivers if d.is_active)
    inactive_count = len(drivers) - active_count
    can_edit = request.user.is_superuser or get_user_role(request.user) in {ROLE_ADMIN, ROLE_TRANSPORT}
    return render(request, "logistics/drivers.html", {
        "drivers": drivers,
        "can_edit": can_edit,
        "active_count": active_count,
        "inactive_count": inactive_count,
    })


@login_required
@role_required(ROLE_ADMIN, ROLE_TRANSPORT)
def driver_edit(request, pk):
    driver = get_object_or_404(Driver, pk=pk)
    if request.method == "POST":
        driver.full_name       = request.POST.get("full_name", driver.full_name).strip()
        driver.phone           = request.POST.get("phone", driver.phone).strip()
        driver.telegram_chat_id = request.POST.get("telegram_chat_id", driver.telegram_chat_id).strip()
        driver.license_number  = request.POST.get("license_number", driver.license_number).strip()
        driver.license_category = request.POST.get("license_category", driver.license_category).strip()
        driver.notes           = request.POST.get("notes", driver.notes).strip()
        driver.is_active       = request.POST.get("is_active") == "on"
        photo = request.FILES.get("photo")
        if photo:
            driver.photo = photo
        driver.save()
        messages.success(request, f"Водитель {driver.full_name} обновлён.")
        return redirect("driver_list")
    return render(request, "logistics/driver_edit.html", {"driver": driver})


# ── Cargo items ───────────────────────────────────────────────────────────────

@login_required
@role_required(ROLE_ADMIN, ROLE_OPERATOR)
def cargo_item_toggle(request, pk, item_pk):
    from django.http import JsonResponse
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    request_obj = get_object_or_404(LogisticsRequest, pk=pk)
    item = get_object_or_404(CargoItem, pk=item_pk, request=request_obj)
    item.needs_supply = not item.needs_supply
    item.save(update_fields=["needs_supply"])
    return JsonResponse({"needs_supply": item.needs_supply})


@login_required
@role_required(ROLE_ADMIN, ROLE_OPERATOR, ROLE_SUPPLY)
def cargo_item_toggle_cz(request, pk, item_pk):
    from django.http import JsonResponse
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    request_obj = get_object_or_404(LogisticsRequest, pk=pk)
    item = get_object_or_404(CargoItem, pk=item_pk, request=request_obj)
    item.needs_cz = not item.needs_cz
    item.save(update_fields=["needs_cz"])
    return JsonResponse({"needs_cz": item.needs_cz})


@login_required
@role_required(ROLE_ADMIN, ROLE_OPERATOR, ROLE_SUPPLY)
def cargo_item_supply_date(request, pk, item_pk):
    from django.http import JsonResponse
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    request_obj = get_object_or_404(LogisticsRequest, pk=pk)
    item = get_object_or_404(CargoItem, pk=item_pk, request=request_obj)
    new_date = parse_date(request.POST.get("supply_date") or "") or None
    item.supply_date = new_date
    item.save(update_fields=["supply_date"])

    # Уведомления от сотрудника снабжения
    if new_date and get_user_role(request.user) == ROLE_SUPPLY:
        # → Транспортный отдел: подготовить автомобиль
        create_role_notification(
            ROLE_TRANSPORT,
            request_obj,
            f"Заявка {request_obj.request_number} ({request_obj.client_name}): "
            f"«{item.name[:60]}» поступит {new_date:%d.%m.%Y} — закажите автомобиль.",
        )
        # → Оператор: дата поступления позже плановой доставки
        if request_obj.planned_delivery_date and new_date > request_obj.planned_delivery_date:
            create_role_notification(
                ROLE_OPERATOR,
                request_obj,
                f"Заявка {request_obj.request_number} ({request_obj.client_name}): "
                f"дата поступления «{item.name[:50]}» ({new_date:%d.%m.%Y}) позже плановой доставки "
                f"({request_obj.planned_delivery_date:%d.%m.%Y}) — согласуйте с клиентом новую дату поставки.",
            )

    existing_pickup = (
        SupplyPickupRequest.objects
        .filter(source_cargo_item=item)
        .exclude(status=SupplyPickupRequest.STATUS_DELIVERED)
        .first()
    )
    return JsonResponse({
        "supply_date": item.supply_date.strftime("%d.%m.%Y") if item.supply_date else "",
        "pickup_request_id": existing_pickup.pk if existing_pickup else None,
        "pickup_request_number": existing_pickup.request_number if existing_pickup else None,
    })


@login_required
def cargo_item_toggle_stocked(request, pk, item_pk):
    from django.http import JsonResponse
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    if not request.user.is_superuser and get_user_role(request.user) not in {ROLE_ADMIN, ROLE_WAREHOUSE}:
        return JsonResponse({"error": "forbidden"}, status=403)
    request_obj = get_object_or_404(LogisticsRequest, pk=pk)
    item = get_object_or_404(CargoItem, pk=item_pk, request=request_obj)
    item.is_stocked = not item.is_stocked
    item.save(update_fields=["is_stocked"])

    # Auto-advance to ГОТОВ К ОТГРУЗКЕ when all supply items are stocked
    supply_items = list(request_obj.cargo_items.filter(needs_supply=True))
    all_stocked = bool(supply_items) and all(ci.is_stocked for ci in supply_items)
    auto_advanced = False
    if all_stocked and request_obj.status in {STATUS_WAITING_ARRIVAL, STATUS_IN_WAREHOUSE, STATUS_CZ_CHECK}:
        if not request_obj.warehouse_arrival_date:
            request_obj.warehouse_arrival_date = timezone.localdate()
            request_obj.save(update_fields=["warehouse_arrival_date", "updated_at"])
        try:
            change_request_status(
                request_obj,
                STATUS_READY_TO_SHIP,
                request.user,
                "Все товары оприходованы — статус обновлён автоматически",
            )
            auto_advanced = True
        except ValidationError:
            pass

    return JsonResponse({
        "is_stocked": item.is_stocked,
        "all_stocked": all_stocked,
        "auto_advanced": auto_advanced,
    })


@login_required
@role_required(ROLE_ADMIN, ROLE_OPERATOR)
def cargo_item_add(request, pk):
    if request.method != "POST":
        return redirect("request_detail", pk=pk)
    request_obj = get_object_or_404(LogisticsRequest, pk=pk)
    name = request.POST.get("name", "").strip()
    qty = request.POST.get("qty", "").strip()
    if name:
        last_pos = request_obj.cargo_items.count()
        CargoItem.objects.create(
            request=request_obj, name=name, qty=qty,
            needs_supply=True, position=last_pos,
        )
    return redirect(request_obj)


@login_required
@role_required(ROLE_ADMIN, ROLE_OPERATOR)
def cargo_item_delete(request, pk, item_pk):
    if request.method != "POST":
        return redirect("request_detail", pk=pk)
    request_obj = get_object_or_404(LogisticsRequest, pk=pk)
    CargoItem.objects.filter(pk=item_pk, request=request_obj).delete()
    return redirect(request_obj)


# ── Admin panel ────────────────────────────────────────────────────────────────

@login_required
@role_required(ROLE_ADMIN, ROLE_MANAGER)
def admin_panel(request):
    from django.db.models import Count
    from django.utils.timezone import now as tz_now

    today = tz_now().date()

    all_requests = LogisticsRequest.objects.all()

    # ── headline numbers ───────────────────────────────────────────────────────
    active_qs = all_requests.exclude(status__in=COMPLETED_STATUSES)
    active_count   = active_qs.count()
    problem_count  = all_requests.filter(status=STATUS_PROBLEM).count()
    overdue_count  = active_qs.filter(
        planned_delivery_date__lt=today
    ).exclude(status=STATUS_PROBLEM).count()

    # ── vehicles & drivers ─────────────────────────────────────────────────────
    vehicles_total  = Vehicle.objects.count()
    vehicles_active = Vehicle.objects.filter(is_active=True).count()
    drivers_total   = Driver.objects.count()
    drivers_active  = Driver.objects.filter(is_active=True).count()

    # ── status breakdown (non-zero only) ───────────────────────────────────────
    status_labels = dict(STATUS_CHOICES)
    status_counts_qs = (
        all_requests
        .exclude(status__in=(STATUS_CLOSED, STATUS_CANCELLED))
        .values("status")
        .annotate(cnt=Count("id"))
        .order_by("-cnt")
    )
    status_breakdown = [
        {
            "status": row["status"],
            "label":  status_labels.get(row["status"], row["status"]),
            "count":  row["cnt"],
        }
        for row in status_counts_qs
        if row["cnt"] > 0
    ]

    # ── recent 10 requests ─────────────────────────────────────────────────────
    recent_requests = (
        all_requests
        .select_related("assigned_driver")
        .order_by("-updated_at")[:10]
    )

    return render(request, "logistics/admin_panel.html", {
        "active_count":    active_count,
        "problem_count":   problem_count,
        "overdue_count":   overdue_count,
        "vehicles_total":  vehicles_total,
        "vehicles_active": vehicles_active,
        "drivers_total":   drivers_total,
        "drivers_active":  drivers_active,
        "status_breakdown": status_breakdown,
        "recent_requests": recent_requests,
    })
