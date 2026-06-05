from .models import Notification


def create_role_notification(role, request_obj, message, pickup_request=None):
    return Notification.objects.create(
        recipient_role=role,
        request=request_obj,
        pickup_request=pickup_request,
        message=message,
    )


def create_user_notification(user, request_obj, message):
    """Персональное уведомление конкретному пользователю (не по роли).

    Если у пользователя есть зарегистрированные FCM-токены — отправляет
    push-уведомление через Firebase Cloud Messaging.
    """
    notif = Notification.objects.create(
        recipient_user=user,
        request=request_obj,
        message=message,
    )
    # Push через FCM (если firebase настроен и у пользователя есть токены)
    try:
        from apps.api.services import send_push_to_user
        send_push_to_user(
            user,
            title="Единый Контур",
            body=message,
            request_id=request_obj.id if request_obj else None,
        )
    except Exception:
        pass  # Push — не критично; не ломаем основной flow
    return notif


def notify_viewers(request_obj, message):
    """Уведомить всех наблюдателей (viewer_users) заявки.

    Используется для значимых событий по заявке: смена статуса,
    появление проблемы, изменение плановых дат.
    """
    if not request_obj or not request_obj.pk:
        return []
    viewers = list(request_obj.viewer_users.all())
    return [create_user_notification(v, request_obj, message) for v in viewers]
