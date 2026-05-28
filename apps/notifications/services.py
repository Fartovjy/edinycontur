from .models import Notification


def create_role_notification(role, request_obj, message, pickup_request=None):
    return Notification.objects.create(
        recipient_role=role,
        request=request_obj,
        pickup_request=pickup_request,
        message=message,
    )


def create_user_notification(user, request_obj, message):
    """Персональное уведомление конкретному пользователю (не по роли)."""
    return Notification.objects.create(
        recipient_user=user,
        request=request_obj,
        message=message,
    )


def notify_viewers(request_obj, message):
    """Уведомить всех наблюдателей (viewer_users) заявки.

    Используется для значимых событий по заявке: смена статуса,
    появление проблемы, изменение плановых дат.
    """
    if not request_obj or not request_obj.pk:
        return []
    viewers = list(request_obj.viewer_users.all())
    return [create_user_notification(v, request_obj, message) for v in viewers]
