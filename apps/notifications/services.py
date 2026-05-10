from .models import Notification


def create_role_notification(role, request_obj, message):
    return Notification.objects.create(
        recipient_role=role,
        request=request_obj,
        message=message,
    )
