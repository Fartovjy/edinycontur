from .models import Notification


def create_role_notification(role, request_obj, message, pickup_request=None):
    return Notification.objects.create(
        recipient_role=role,
        request=request_obj,
        pickup_request=pickup_request,
        message=message,
    )
