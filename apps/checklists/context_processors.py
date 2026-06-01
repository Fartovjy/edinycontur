"""Context processor: количество активных дел для текущей роли."""

from apps.accounts.permissions import get_user_role
from apps.logistics.constants import STATUS_CANCELLED, STATUS_CLOSED, STATUS_DELIVERED

from .models import RequestChecklistItem


COMPLETED_STATUSES = {STATUS_DELIVERED, STATUS_CLOSED, STATUS_CANCELLED}


def current_tasks_count(request):
    """Возвращает кол-во заявок с невыполненными пунктами текущей роли."""
    if not request.user.is_authenticated:
        return {}
    role = get_user_role(request.user)
    if not role:
        return {"current_tasks_count": 0}
    count = (
        RequestChecklistItem.objects
        .filter(role=role, is_done=False)
        .exclude(request__status__in=COMPLETED_STATUSES)
        .values("request_id")
        .distinct()
        .count()
    )
    return {"current_tasks_count": count}
