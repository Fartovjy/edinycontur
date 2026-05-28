from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse

from apps.accounts.permissions import get_user_role

from .models import Notification


@login_required
def unread_count(request):
    """AJAX endpoint: возвращает количество непрочитанных уведомлений
    для текущего пользователя (по роли + персональные).
    Используется для звукового уведомления на фронте."""
    role = get_user_role(request.user)
    count = Notification.objects.filter(
        Q(recipient_user=request.user)
        | Q(recipient_role=role, recipient_user__isnull=True),
        is_read=False,
    ).count()
    return JsonResponse({"count": count})
