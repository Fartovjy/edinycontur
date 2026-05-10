from apps.accounts.permissions import get_user_role

from .models import Notification


def unread_notifications(request):
    if not request.user.is_authenticated:
        return {}

    role = get_user_role(request.user)
    notifications = Notification.objects.filter(
        recipient_role=role,
        is_read=False,
    ).select_related("request")

    return {
        "unread_notifications": notifications[:5],
        "unread_notifications_count": notifications.count(),
    }
