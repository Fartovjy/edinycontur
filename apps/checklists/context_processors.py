"""Context processor: количество активных дел для текущей роли."""

from apps.accounts.constants import ROLE_DRIVER, ROLE_OPERATOR
from apps.accounts.permissions import get_user_role
from apps.logistics.constants import STATUS_CANCELLED, STATUS_CLOSED, STATUS_DELIVERED

from .models import RequestChecklistItem, UserTask


COMPLETED_STATUSES = {STATUS_DELIVERED, STATUS_CLOSED, STATUS_CANCELLED}


def current_tasks_count(request):
    """Возвращает кол-во заявок с невыполненными пунктами текущей роли.

    Фильтрация «своих» заявок соответствует логике current_tasks view:
    - Оператор: только заявки, созданные им самим.
    - Водитель: только заявки, где он назначен.
    - Остальные роли: все заявки.
    """
    if not request.user.is_authenticated:
        return {}
    role = get_user_role(request.user)
    if not role:
        return {"current_tasks_count": 0}

    qs = (
        RequestChecklistItem.objects
        .filter(role=role, is_done=False)
        .exclude(request__status__in=COMPLETED_STATUSES)
    )

    if role == ROLE_OPERATOR:
        qs = qs.filter(request__created_by=request.user)
    elif role == ROLE_DRIVER:
        qs = qs.filter(request__assigned_driver__user=request.user)

    count = qs.values("request_id").distinct().count()
    user_tasks_count = UserTask.objects.filter(user=request.user, is_done=False).count()
    return {"current_tasks_count": count + user_tasks_count}
