"""Views для чек-листов."""

from collections import OrderedDict

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.accounts.constants import ROLE_ADMIN, ROLE_DRIVER, ROLE_OPERATOR
from apps.accounts.permissions import get_user_role
from apps.logistics.constants import STATUS_CANCELLED, STATUS_CLOSED, STATUS_DELIVERED
from apps.logistics.models import LogisticsRequest

from .models import RequestChecklistItem


def _can_toggle(user, item):
    """Toggle разрешён, если пользователь — superuser, админ, или его роль = роли пункта."""
    if user.is_superuser:
        return True
    role = get_user_role(user)
    if role == ROLE_ADMIN:
        return True
    return role == item.role


@login_required
def checklist_item_toggle(request, item_pk):
    """AJAX: переключить статус пункта чек-листа."""
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)

    item = get_object_or_404(RequestChecklistItem, pk=item_pk)
    if not _can_toggle(request.user, item):
        raise PermissionDenied

    item.is_done = not item.is_done
    if item.is_done:
        item.checked_by = request.user
        item.checked_at = timezone.now()
    else:
        item.checked_by = None
        item.checked_at = None
    item.save(update_fields=["is_done", "checked_by", "checked_at"])

    full_name = ""
    if item.checked_by:
        full_name = item.checked_by.get_full_name() or item.checked_by.username

    return JsonResponse({
        "is_done": item.is_done,
        "checked_by": full_name,
        "checked_at": item.checked_at.strftime("%d.%m.%Y %H:%M") if item.checked_at else None,
    })


COMPLETED_STATUSES = {STATUS_DELIVERED, STATUS_CLOSED, STATUS_CANCELLED}


@login_required
def current_tasks(request):
    """Страница «Текущие дела»: все активные заявки текущей роли,
    у которых есть невыполненные пункты чек-листа."""
    user = request.user
    role = get_user_role(user)
    if not role:
        return render(request, "checklists/current_tasks.html",
                      {"blocks": [], "role_label": "", "role_code": role})

    # ID заявок, где есть невыполненные пункты для роли пользователя
    items_qs = (
        RequestChecklistItem.objects
        .filter(role=role, is_done=False)
        .exclude(request__status__in=COMPLETED_STATUSES)
    )

    # Фильтрация «своих» заявок по аналогии с основным списком:
    # Оператор видит только заявки, которые сам создал.
    # Водитель — только заявки, где он назначен водителем.
    # Остальные роли (Снабжение, Транспорт, Склад) видят все заявки.
    if role == ROLE_OPERATOR:
        items_qs = items_qs.filter(request__created_by=user)
    elif role == ROLE_DRIVER:
        items_qs = items_qs.filter(request__assigned_driver__user=user)

    candidate_ids = items_qs.values_list("request_id", flat=True).distinct()

    requests_qs = (
        LogisticsRequest.objects
        .filter(pk__in=list(candidate_ids))
        .order_by("-priority", "planned_delivery_date", "-updated_at")
    )

    # Для каждой заявки собрать чек-лист её роли
    role_labels = {
        "admin": "Администратор", "operator": "Оператор", "supply": "Снабжение",
        "transport": "Транспорт", "warehouse": "Склад", "driver": "Водитель",
        "manager": "Руководитель", "viewer": "Наблюдатель",
    }
    blocks = []
    can_toggle = user.is_superuser or role == ROLE_ADMIN

    items_by_req = OrderedDict()
    items_qs = (
        RequestChecklistItem.objects
        .filter(request__in=requests_qs, role=role)
        .select_related("checked_by")
        .order_by("request_id", "order", "id")
    )
    for it in items_qs:
        items_by_req.setdefault(it.request_id, []).append(it)

    for req in requests_qs:
        items = items_by_req.get(req.pk, [])
        done = sum(1 for it in items if it.is_done)
        blocks.append({
            "request_obj": req,
            "items": items,
            "done_count": done,
            "total": len(items),
            "remaining": len(items) - done,
            "role_code": role,
            "role_label": role_labels.get(role, role),
            "editable": can_toggle or True,  # своя роль — всегда editable
        })

    return render(request, "checklists/current_tasks.html", {
        "blocks": blocks,
        "role_label": role_labels.get(role, role),
        "role_code": role,
    })
