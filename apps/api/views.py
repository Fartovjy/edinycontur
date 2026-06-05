"""Views мобильного REST API."""

import logging

from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.constants import ROLE_VIEWER
from apps.logistics.constants import (
    STATUS_CANCELLED,
    STATUS_CLOSED,
    STATUS_DELIVERED,
)
from apps.logistics.models import LogisticsRequest
from apps.notifications.models import Notification

from .models import DeviceToken
from .permissions import IsMobileViewerAuthenticated
from .serializers import (
    DeviceTokenRegisterSerializer,
    LoginSerializer,
    NotificationSerializer,
    RequestDetailSerializer,
    RequestListSerializer,
    UserProfileSerializer,
)

logger = logging.getLogger(__name__)

COMPLETED_STATUSES = [STATUS_DELIVERED, STATUS_CLOSED, STATUS_CANCELLED]


# ─── Auth ──────────────────────────────────────────────────────────────────────

class LoginView(APIView):
    """POST /api/v1/auth/login/ — получить токен."""
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            "token": token.key,
            "user": UserProfileSerializer(user).data,
        })


class LogoutView(APIView):
    """POST /api/v1/auth/logout/ — удалить токен."""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsMobileViewerAuthenticated]

    def post(self, request):
        try:
            request.user.auth_token.delete()
        except Exception:
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─── Me ────────────────────────────────────────────────────────────────────────

class MeView(APIView):
    """GET /api/v1/me/ — профиль текущего пользователя."""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsMobileViewerAuthenticated]

    def get(self, request):
        return Response(UserProfileSerializer(request.user).data)


# ─── Devices ───────────────────────────────────────────────────────────────────

class DeviceRegisterView(APIView):
    """POST /api/v1/devices/register/ — зарегистрировать FCM-токен."""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsMobileViewerAuthenticated]

    def post(self, request):
        serializer = DeviceTokenRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fcm_token = serializer.validated_data["fcm_token"]
        platform = serializer.validated_data.get("platform", "android")

        # Если токен уже есть у другого пользователя — переназначаем (устройство у нового владельца)
        DeviceToken.objects.filter(fcm_token=fcm_token).exclude(user=request.user).delete()

        obj, created = DeviceToken.objects.get_or_create(
            fcm_token=fcm_token,
            defaults={"user": request.user, "platform": platform},
        )
        if not created:
            # Обновляем last_seen_at через save() (auto_now)
            obj.save(update_fields=["last_seen_at"])

        return Response({"ok": True, "created": created})


class DeviceUnregisterView(APIView):
    """DELETE /api/v1/devices/<token>/ — удалить токен устройства."""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsMobileViewerAuthenticated]

    def delete(self, request, fcm_token):
        deleted, _ = DeviceToken.objects.filter(
            user=request.user, fcm_token=fcm_token
        ).delete()
        if deleted:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({"error": "Токен не найден."}, status=status.HTTP_404_NOT_FOUND)


# ─── Requests ──────────────────────────────────────────────────────────────────

def _viewer_requests_qs(user):
    """QuerySet заявок доступных наблюдателю."""
    return (
        LogisticsRequest.objects
        .filter(viewer_users=user)
        .select_related("warehouse", "assigned_vehicle", "assigned_driver")
        .prefetch_related("problems")
        .order_by("-updated_at")
    )


class RequestListView(APIView):
    """GET /api/v1/requests/ — список заявок наблюдателя."""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsMobileViewerAuthenticated]

    def get(self, request):
        qs = _viewer_requests_qs(request.user)

        # Фильтр для инкрементального синка: ?since=<ISO8601>
        since = request.query_params.get("since")
        if since:
            try:
                from django.utils.dateparse import parse_datetime
                since_dt = parse_datetime(since)
                if since_dt and timezone.is_naive(since_dt):
                    since_dt = timezone.make_aware(since_dt)
                if since_dt:
                    qs = qs.filter(updated_at__gte=since_dt)
            except Exception:
                pass

        serializer = RequestListSerializer(qs, many=True)
        return Response({
            "results": serializer.data,
            "server_time": timezone.now().isoformat(),
            "count": len(serializer.data),
        })


class RequestDetailView(APIView):
    """GET /api/v1/requests/<id>/ — детали заявки."""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsMobileViewerAuthenticated]

    def get(self, request, pk):
        try:
            obj = (
                LogisticsRequest.objects
                .filter(viewer_users=request.user, pk=pk)
                .select_related("warehouse", "assigned_vehicle", "assigned_driver")
                .prefetch_related(
                    "cargo_items",
                    "status_history__changed_by",
                    "problems",
                )
                .get()
            )
        except LogisticsRequest.DoesNotExist:
            return Response({"error": "Заявка не найдена."}, status=status.HTTP_404_NOT_FOUND)

        serializer = RequestDetailSerializer(obj)
        return Response(serializer.data)


# ─── Notifications ─────────────────────────────────────────────────────────────

class NotificationListView(APIView):
    """GET /api/v1/notifications/ — персональные уведомления наблюдателя."""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsMobileViewerAuthenticated]

    def get(self, request):
        qs = (
            Notification.objects
            .filter(recipient_user=request.user)
            .select_related("request")
            .order_by("-created_at")[:100]
        )
        serializer = NotificationSerializer(qs, many=True)
        return Response({"results": serializer.data, "count": len(serializer.data)})


class NotificationReadView(APIView):
    """POST /api/v1/notifications/<id>/read/ — пометить уведомление прочитанным."""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsMobileViewerAuthenticated]

    def post(self, request, pk):
        updated = Notification.objects.filter(
            recipient_user=request.user, pk=pk
        ).update(is_read=True)
        if updated:
            return Response({"ok": True})
        return Response({"error": "Уведомление не найдено."}, status=status.HTTP_404_NOT_FOUND)
