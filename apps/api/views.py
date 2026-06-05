"""Views мобильного REST API."""

import logging

from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.constants import ROLE_DRIVER, ROLE_TRANSPORT, ROLE_VIEWER
from apps.logistics.constants import (
    STATUS_CANCELLED,
    STATUS_CLOSED,
    STATUS_DELIVERED,
    STATUS_PROBLEM,
    STATUS_TRANSPORT_ASSIGNED,
)
from apps.logistics.models import LogisticsRequest
from apps.logistics.services import change_request_status
from apps.notifications.models import Notification
from apps.notifications.services import create_role_notification
from apps.problems.models import ProblemReport

from .models import DeviceToken, RequestPhoto
from .permissions import IsMobileDriverAuthenticated, IsMobileViewerAuthenticated
from .serializers import (
    BreakdownSerializer,
    DeviceTokenRegisterSerializer,
    LoginSerializer,
    NotificationSerializer,
    OdometerSerializer,
    RequestDetailSerializer,
    RequestListSerializer,
    RequestPhotoSerializer,
    StatusChangeSerializer,
    TripDetailSerializer,
    TripListSerializer,
    UserProfileSerializer,
    DRIVER_STATUS_TRANSITIONS,
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


# ═══════════════════════════════════════════════════════════════════════════════
# Driver API  /api/v1/driver/...
# ═══════════════════════════════════════════════════════════════════════════════

def _driver_trips_qs(user):
    """QuerySet рейсов для конкретного водителя (только заявки, где он назначен)."""
    return (
        LogisticsRequest.objects
        .filter(assigned_driver__user=user)
        .exclude(status__in=[STATUS_CANCELLED, STATUS_CLOSED])
        .select_related("warehouse", "assigned_vehicle", "assigned_driver")
        .prefetch_related("problems")
        .order_by("planned_delivery_date", "-priority")
    )


class DriverTripListView(APIView):
    """
    GET /api/v1/driver/trips/
        ?date=2026-06-05   — рейсы на конкретный день (по planned_ship_date ИЛИ planned_delivery_date)
        без параметра      — сегодняшние рейсы
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsMobileDriverAuthenticated]

    def get(self, request):
        from django.utils.dateparse import parse_date

        date_param = request.query_params.get("date")
        if date_param:
            target_date = parse_date(date_param)
            if not target_date:
                return Response({"error": "Неверный формат даты. Используйте YYYY-MM-DD."},
                                status=status.HTTP_400_BAD_REQUEST)
        else:
            target_date = timezone.localdate()

        qs = _driver_trips_qs(request.user).filter(
            Q(planned_ship_date=target_date) | Q(planned_delivery_date=target_date)
        )

        serializer = TripListSerializer(qs, many=True)
        return Response({
            "date": str(target_date),
            "results": serializer.data,
            "count": len(serializer.data),
        })


class DriverTripDetailView(APIView):
    """GET /api/v1/driver/trips/<id>/ — детальная карточка рейса."""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsMobileDriverAuthenticated]

    def get(self, request, pk):
        try:
            obj = (
                _driver_trips_qs(request.user)
                .filter(pk=pk)
                .prefetch_related(
                    "cargo_items",
                    "status_history__changed_by",
                    "problems",
                    "driver_photos__uploaded_by",
                )
                .get()
            )
        except LogisticsRequest.DoesNotExist:
            return Response({"error": "Заявка не найдена."}, status=status.HTTP_404_NOT_FOUND)

        serializer = TripDetailSerializer(obj, context={"request": request})
        return Response(serializer.data)


class DriverTripStatusView(APIView):
    """POST /api/v1/driver/trips/<id>/status/ — сменить статус заявки."""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsMobileDriverAuthenticated]

    def post(self, request, pk):
        try:
            obj = _driver_trips_qs(request.user).filter(pk=pk).get()
        except LogisticsRequest.DoesNotExist:
            return Response({"error": "Заявка не найдена."}, status=status.HTTP_404_NOT_FOUND)

        serializer = StatusChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data["status"]
        comment    = serializer.validated_data.get("comment", "")

        # Проверяем, что водителю разрешён именно этот переход
        allowed_next = DRIVER_STATUS_TRANSITIONS.get(obj.status)
        if allowed_next != new_status:
            return Response(
                {"error": f"Недопустимый переход: {obj.status} → {new_status}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            change_request_status(obj, new_status, request.user, comment=comment)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"ok": True, "status": new_status})


class DriverTripOdometerView(APIView):
    """POST /api/v1/driver/trips/<id>/odometer/ — записать показание одометра."""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsMobileDriverAuthenticated]

    def post(self, request, pk):
        try:
            obj = _driver_trips_qs(request.user).filter(pk=pk).get()
        except LogisticsRequest.DoesNotExist:
            return Response({"error": "Заявка не найдена."}, status=status.HTTP_404_NOT_FOUND)

        serializer = OdometerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        km = serializer.validated_data["odometer_km"]

        # Сохраняем как запись в истории статусов с префиксом "odometer:"
        from apps.logistics.models import RequestStatusHistory
        RequestStatusHistory.objects.create(
            request=obj,
            old_status=obj.status,
            new_status=obj.status,
            changed_by=request.user,
            comment=f"odometer:{km}",
        )

        # Обновляем одометр автомобиля, если он назначен
        if obj.assigned_vehicle:
            vehicle = obj.assigned_vehicle
            if not vehicle.odometer_km or vehicle.odometer_km < km:
                vehicle.odometer_km = km
                vehicle.save(update_fields=["odometer_km"])

        return Response({"ok": True, "odometer_km": km})


class DriverTripPhotosView(APIView):
    """
    GET  /api/v1/driver/trips/<id>/photos/ — список фото заявки
    POST /api/v1/driver/trips/<id>/photos/ — загрузить фото (multipart)
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsMobileDriverAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, pk):
        try:
            obj = _driver_trips_qs(request.user).filter(pk=pk).get()
        except LogisticsRequest.DoesNotExist:
            return Response({"error": "Заявка не найдена."}, status=status.HTTP_404_NOT_FOUND)

        photos = obj.driver_photos.select_related("uploaded_by").order_by("created_at")
        serializer = RequestPhotoSerializer(photos, many=True, context={"request": request})
        return Response({"results": serializer.data, "count": len(serializer.data)})

    def post(self, request, pk):
        try:
            obj = _driver_trips_qs(request.user).filter(pk=pk).get()
        except LogisticsRequest.DoesNotExist:
            return Response({"error": "Заявка не найдена."}, status=status.HTTP_404_NOT_FOUND)

        photo_file = request.FILES.get("file")
        if not photo_file:
            return Response({"error": "Файл не передан (поле «file»)."}, status=status.HTTP_400_BAD_REQUEST)

        photo_type = request.data.get("photo_type", RequestPhoto.PHOTO_LOADING)
        if photo_type not in {RequestPhoto.PHOTO_LOADING, RequestPhoto.PHOTO_DELIVERY, RequestPhoto.PHOTO_PROBLEM}:
            photo_type = RequestPhoto.PHOTO_LOADING

        photo_obj = RequestPhoto.objects.create(
            request=obj,
            uploaded_by=request.user,
            photo=photo_file,
            photo_type=photo_type,
        )
        serializer = RequestPhotoSerializer(photo_obj, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class DriverBreakdownView(APIView):
    """POST /api/v1/driver/breakdown/ — сообщить о поломке автомобиля."""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsMobileDriverAuthenticated]

    def post(self, request):
        serializer = BreakdownSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        description = data["description"]
        request_id  = data.get("request_id")

        # Определяем заявку (если передана)
        req_obj = None
        if request_id:
            try:
                req_obj = _driver_trips_qs(request.user).filter(pk=request_id).get()
            except LogisticsRequest.DoesNotExist:
                return Response({"error": "Заявка не найдена."}, status=status.HTTP_404_NOT_FOUND)

        # Создаём ProblemReport
        problem = ProblemReport.objects.create(
            request=req_obj or _get_or_create_dummy_request(request.user),
            problem_type=ProblemReport.TRANSPORT_DELAY,
            description=description,
            created_by=request.user,
        )

        # Уведомляем транспортный отдел
        driver_name = request.user.get_full_name() or request.user.username
        msg = f"🔴 Поломка автомобиля. Водитель: {driver_name}. {description}"
        if req_obj:
            msg = f"🔴 Поломка по заявке {req_obj.request_number}. Водитель: {driver_name}. {description}"
        create_role_notification(ROLE_TRANSPORT, req_obj, msg)

        # Если есть заявка — переводим в STATUS_PROBLEM
        if req_obj and req_obj.status not in (STATUS_PROBLEM, STATUS_DELIVERED, STATUS_CANCELLED, STATUS_CLOSED):
            try:
                change_request_status(req_obj, STATUS_PROBLEM, request.user, comment=description)
            except Exception:
                pass  # не критично, если переход недопустим

        return Response({"ok": True, "problem_id": problem.pk}, status=status.HTTP_201_CREATED)


def _get_or_create_dummy_request(user):
    """Возвращает любую активную заявку водителя, или первую попавшуюся, для ProblemReport.

    ProblemReport требует ForeignKey на LogisticsRequest. Если водитель не передал
    request_id, используем первую заявку в его очереди (или последнюю активную).
    """
    qs = LogisticsRequest.objects.filter(assigned_driver__user=user).order_by("-created_at")
    obj = qs.first()
    if obj:
        return obj
    # Fallback — берём первую заявку вообще (не должно происходить на практике)
    return LogisticsRequest.objects.order_by("pk").first()
