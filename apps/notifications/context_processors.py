from django.db.models import Q
from django.utils import timezone

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

    # Для Транспортного отдела: два вида ожидающих заявок
    pending_transport = []           # нет даты отгрузки — перетаскиваемые
    pending_transport_no_vehicle = []  # дата есть, машина не назначена — напоминание
    if role == ROLE_TRANSPORT or (hasattr(request.user, "is_superuser") and request.user.is_superuser):
        try:
            from apps.logistics.models import LogisticsRequest
            from apps.logistics.constants import (
                STATUS_READY_TO_SHIP,
                STATUS_TRANSPORT_ASSIGNED,
            )
            today = timezone.localdate()
            base_qs = LogisticsRequest.objects.filter(
                status__in=[STATUS_READY_TO_SHIP, STATUS_TRANSPORT_ASSIGNED],
                is_archived=False,
            )
            pending_transport = list(
                base_qs
                .filter(planned_ship_date__isnull=True)
                .order_by("planned_delivery_date", "-updated_at")
                .only("id", "request_number", "client_name", "planned_delivery_date", "status")
                [:30]
            )
            pending_transport_no_vehicle = list(
                base_qs
                .filter(
                    planned_ship_date__isnull=False,
                    planned_ship_date__gte=today,
                    assigned_vehicle__isnull=True,
                )
                .order_by("planned_ship_date", "-updated_at")
                .only("id", "request_number", "client_name", "planned_ship_date", "status")
                [:30]
            )
        except Exception:
            pending_transport = []
            pending_transport_no_vehicle = []

    return {
        "unread_notifications": notifications[:5],
        "unread_notifications_count": notifications.count(),
        "pending_transport": pending_transport,
        "pending_transport_no_vehicle": pending_transport_no_vehicle,
    }
