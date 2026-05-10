from django.core.exceptions import ValidationError
from django.db import transaction

from .constants import (
    STATUS_CLOSED,
    STATUS_CANCELLED,
    STATUS_CREATED,
    STATUS_CZ_CHECK,
    STATUS_DELIVERED,
    STATUS_IN_TRANSIT,
    STATUS_IN_WAREHOUSE,
    STATUS_PROBLEM,
    STATUS_READY_TO_SHIP,
    STATUS_SHIPPED,
    STATUS_TRANSPORT_ASSIGNED,
    STATUS_WAITING_ARRIVAL,
    STATUS_WAITING_SUPPLY,
)
from .models import RequestStatusHistory


ALLOWED_STATUS_TRANSITIONS = {
    STATUS_CREATED: {STATUS_WAITING_SUPPLY, STATUS_PROBLEM},
    STATUS_WAITING_SUPPLY: {STATUS_WAITING_ARRIVAL, STATUS_PROBLEM},
    STATUS_WAITING_ARRIVAL: {STATUS_IN_WAREHOUSE, STATUS_PROBLEM},
    STATUS_IN_WAREHOUSE: {STATUS_CZ_CHECK, STATUS_PROBLEM},
    STATUS_CZ_CHECK: {STATUS_READY_TO_SHIP, STATUS_PROBLEM},
    STATUS_READY_TO_SHIP: {STATUS_TRANSPORT_ASSIGNED, STATUS_PROBLEM},
    STATUS_TRANSPORT_ASSIGNED: {STATUS_SHIPPED, STATUS_PROBLEM},
    STATUS_SHIPPED: {STATUS_IN_TRANSIT, STATUS_PROBLEM},
    STATUS_IN_TRANSIT: {STATUS_DELIVERED, STATUS_PROBLEM},
    STATUS_DELIVERED: {STATUS_CLOSED, STATUS_PROBLEM},
    STATUS_CLOSED: set(),
    STATUS_CANCELLED: set(),
}

WORKING_STATUSES = {
    STATUS_CREATED,
    STATUS_WAITING_SUPPLY,
    STATUS_WAITING_ARRIVAL,
    STATUS_IN_WAREHOUSE,
    STATUS_CZ_CHECK,
    STATUS_READY_TO_SHIP,
    STATUS_TRANSPORT_ASSIGNED,
    STATUS_SHIPPED,
    STATUS_IN_TRANSIT,
    STATUS_DELIVERED,
}


def get_previous_working_status(request):
    problem_entry = (
        request.status_history.filter(new_status=STATUS_PROBLEM)
        .exclude(old_status__in=["", STATUS_PROBLEM, STATUS_CLOSED, STATUS_CANCELLED])
        .order_by("-created_at")
        .first()
    )
    return problem_entry.old_status if problem_entry else None


def get_allowed_next_statuses(request):
    if request.status == STATUS_PROBLEM:
        previous_status = get_previous_working_status(request)
        allowed = set(WORKING_STATUSES) | {STATUS_CLOSED}
        if previous_status:
            allowed.add(previous_status)
        return allowed
    return ALLOWED_STATUS_TRANSITIONS.get(request.status, set())


def is_status_transition_allowed(request, new_status):
    if request.status == new_status:
        return True
    return new_status in get_allowed_next_statuses(request)


def change_request_status(request, new_status, user, comment=None):
    if request.status == new_status:
        return None

    if not is_status_transition_allowed(request, new_status):
        raise ValidationError(f"Недопустимый переход статуса: {request.status} -> {new_status}")

    old_status = request.status
    changed_by = user if user and getattr(user, "is_authenticated", False) else None

    with transaction.atomic():
        request.status = new_status
        request.save(update_fields=["status", "updated_at"])
        return RequestStatusHistory.objects.create(
            request=request,
            old_status=old_status,
            new_status=new_status,
            changed_by=changed_by,
            comment=comment or "",
        )
