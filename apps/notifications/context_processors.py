from django.db.models import Q

from apps.accounts.constants import ROLE_TRANSPORT
from apps.accounts.permissions import get_user_role

from .models import Notification


def unread_notifications(request):
    if not request.user.is_authenticated:
        return {}

    role = get_user_role(request.user)
    notifications = Notification.objects.filter(
        Q(recipient_user=request.user)
        | Q(recipient_role=role, recipient_user__isnull=True),
        is_read=False,
    ).select_related("request", "pickup_request")

    # Для Транспортного отдела: заявки ожидают в уведомлениях
    pending_transport = []        # нет машины — не перетаскиваемые
    pending_transport_ready = []  # машина есть, нет водителя — перетаскиваемые
    if role == ROLE_TRANSPORT or (hasattr(request.user, "is_superuser") and request.user.is_superuser):
        try:
            from apps.logistics.models import LogisticsRequest
            from apps.logistics.constants import (
                STATUS_READY_TO_SHIP,
                STATUS_TRANSPORT_ASSIGNED,
            )
            base_qs = (
                LogisticsRequest.objects
                .filter(
                    status__in=[STATUS_READY_TO_SHIP, STATUS_TRANSPORT_ASSIGNED],
                    is_archived=False,
                )
                .order_by("planned_delivery_date", "-updated_at")
            )
            pending_transport = list(
                base_qs
                .filter(assigned_vehicle__isnull=True)
                .only("id", "request_number", "client_name", "planned_delivery_date", "status")
                [:30]
            )
            pending_transport_ready = list(
                base_qs
                .filter(assigned_vehicle__isnull=False, assigned_driver__isnull=True)
                .only("id", "request_number", "client_name", "planned_delivery_date", "planned_ship_date", "status")
                [:30]
            )
        except Exception:
            pending_transport = []
            pending_transport_ready = []

    return {
        "unread_notifications": notifications[:5],
        "unread_notifications_count": notifications.count(),
        "pending_transport": pending_transport,
        "pending_transport_ready": pending_transport_ready,
    }
