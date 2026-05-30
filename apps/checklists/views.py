"""Views для чек-листов."""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.accounts.constants import ROLE_ADMIN
from apps.accounts.permissions import get_user_role

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
