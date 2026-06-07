"""DRF-сериализаторы для мобильного API."""

from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework.authtoken.models import Token

from apps.logistics.constants import (
    STATUS_DELIVERED,
    STATUS_IN_TRANSIT,
    STATUS_READY_TO_SHIP,
    STATUS_SHIPPED,
    STATUS_TRANSPORT_ASSIGNED,
)
from apps.logistics.models import (
    CargoItem,
    LogisticsRequest,
    RequestStatusHistory,
)
from apps.notifications.models import Notification
from apps.problems.models import ProblemReport

from .models import RequestPhoto


# ─── Auth ──────────────────────────────────────────────────────────────────────

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(label="Логин")
    password = serializers.CharField(label="Пароль", write_only=True, style={"input_type": "password"})

    def validate(self, data):
        request = self.context.get("request")
        user = authenticate(request, username=data["username"], password=data["password"])
        if not user:
            raise serializers.ValidationError("Неверный логин или пароль.")
        if not user.is_active:
            raise serializers.ValidationError("Аккаунт отключён.")
        profile = getattr(user, "profile", None)
        if not profile:
            raise serializers.ValidationError("Профиль пользователя не найден.")
        if not (user.is_superuser or profile.mobile_access_enabled):
            raise serializers.ValidationError("Мобильный доступ не разрешён для этого пользователя.")
        data["user"] = user
        return data


class UserProfileSerializer(serializers.Serializer):
    """Профиль текущего пользователя."""
    id = serializers.IntegerField(source="pk")
    username = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    full_name = serializers.SerializerMethodField()
    email = serializers.EmailField()
    role = serializers.SerializerMethodField()
    role_display = serializers.SerializerMethodField()

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username

    def get_role(self, obj):
        profile = getattr(obj, "profile", None)
        return profile.role if profile else ""

    def get_role_display(self, obj):
        profile = getattr(obj, "profile", None)
        return profile.get_role_display() if profile else ""


# ─── Device Token ───────────────────────────────────────────────────────────────

class DeviceTokenRegisterSerializer(serializers.Serializer):
    fcm_token = serializers.CharField(max_length=512)
    platform = serializers.ChoiceField(choices=["android", "ios"], default="android")


# ─── Requests (list) ───────────────────────────────────────────────────────────

class RequestListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display")
    priority_display = serializers.CharField(source="get_priority_display")
    has_open_problem = serializers.SerializerMethodField()

    class Meta:
        model = LogisticsRequest
        fields = [
            "id",
            "request_number",
            "client_name",
            "planned_delivery_date",
            "status",
            "status_display",
            "priority",
            "priority_display",
            "has_open_problem",
            "updated_at",
        ]

    def get_has_open_problem(self, obj):
        # Используем prefetch если он есть, иначе — запрос
        if hasattr(obj, "_prefetched_objects_cache") and "problems" in obj._prefetched_objects_cache:
            return any(
                p.status in (ProblemReport.OPEN, ProblemReport.IN_PROGRESS)
                for p in obj._prefetched_objects_cache["problems"]
            )
        return obj.problems.filter(status__in=[ProblemReport.OPEN, ProblemReport.IN_PROGRESS]).exists()


# ─── Requests (detail) ─────────────────────────────────────────────────────────

class StatusHistorySerializer(serializers.ModelSerializer):
    old_status_display = serializers.CharField(source="get_old_status_display")
    new_status_display = serializers.CharField(source="get_new_status_display")
    changed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = RequestStatusHistory
        fields = [
            "id",
            "old_status",
            "old_status_display",
            "new_status",
            "new_status_display",
            "changed_by_name",
            "comment",
            "created_at",
        ]

    def get_changed_by_name(self, obj):
        if obj.changed_by:
            return obj.changed_by.get_full_name() or obj.changed_by.username
        return None


class ProblemSerializer(serializers.ModelSerializer):
    problem_type_display = serializers.CharField(source="get_problem_type_display")
    status_display = serializers.CharField(source="get_status_display")

    class Meta:
        model = ProblemReport
        fields = [
            "id",
            "problem_type",
            "problem_type_display",
            "description",
            "status",
            "status_display",
            "created_at",
        ]


class CargoItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CargoItem
        fields = [
            "id",
            "name",
            "qty",
            "needs_cz",
            "supply_date",
            "is_stocked",
        ]


class RequestDetailSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display")
    priority_display = serializers.CharField(source="get_priority_display")
    cz_status_display = serializers.CharField(source="get_cz_status_display")
    has_open_problem = serializers.SerializerMethodField()
    warehouse_name = serializers.CharField(source="warehouse.name", default=None)
    vehicle_plate = serializers.SerializerMethodField()
    driver_name = serializers.SerializerMethodField()
    status_history = StatusHistorySerializer(many=True, read_only=True)
    open_problems = serializers.SerializerMethodField()
    cargo_items = CargoItemSerializer(many=True, read_only=True)

    class Meta:
        model = LogisticsRequest
        fields = [
            # Идентификация
            "id",
            "request_number",
            "status",
            "status_display",
            "priority",
            "priority_display",
            # Клиент
            "client_name",
            "client_address",
            "client_contact",
            "client_phone",
            "region",
            # Груз
            "cargo_description",
            "cargo_places_count",
            "cargo_weight_kg",
            "cargo_volume_m3",
            "dimensions_text",
            # Склад
            "warehouse_name",
            # Даты
            "supply_eta_date",
            "warehouse_arrival_date",
            "planned_ship_date",
            "actual_ship_date",
            "planned_delivery_date",
            "actual_delivery_date",
            "created_at",
            "updated_at",
            # Транспорт
            "vehicle_plate",
            "driver_name",
            # ЧЗ
            "cz_required",
            "cz_status",
            "cz_status_display",
            "cz_comment",
            # Флаги
            "has_open_problem",
            # Вложенные
            "status_history",
            "open_problems",
            "cargo_items",
        ]

    def get_has_open_problem(self, obj):
        return obj.problems.filter(status__in=[ProblemReport.OPEN, ProblemReport.IN_PROGRESS]).exists()

    def get_vehicle_plate(self, obj):
        return obj.assigned_vehicle.plate_number if obj.assigned_vehicle else None

    def get_driver_name(self, obj):
        if obj.assigned_driver:
            return obj.assigned_driver.full_name or str(obj.assigned_driver)
        return None

    def get_open_problems(self, obj):
        qs = obj.problems.filter(status__in=[ProblemReport.OPEN, ProblemReport.IN_PROGRESS])
        return ProblemSerializer(qs, many=True).data


# ─── Driver: allowed status transitions ────────────────────────────────────────

# Переходы, которые ВОДИТЕЛЬ может делать самостоятельно
DRIVER_STATUS_TRANSITIONS = {
    STATUS_READY_TO_SHIP:      STATUS_SHIPPED,    # водитель загрузился напрямую
    STATUS_TRANSPORT_ASSIGNED: STATUS_SHIPPED,
    STATUS_SHIPPED:            STATUS_IN_TRANSIT,
    STATUS_IN_TRANSIT:         STATUS_DELIVERED,
}

# Кнопка-действие — что водитель нажимает, чтобы перейти в следующий статус
DRIVER_ACTION_DISPLAY = {
    STATUS_SHIPPED:    "Загрузился. В пути",
    STATUS_IN_TRANSIT: "Разгрузился. В пути",
    STATUS_DELIVERED:  "На базе. Свободен",
}

# Переходы, требующие ввода пробега перед подтверждением
DRIVER_ODOMETER_REQUIRED = {STATUS_IN_TRANSIT}

# Алиас для list-serializer (следующее действие в карточке)
STATUS_DISPLAY = DRIVER_ACTION_DISPLAY


# ─── Driver: RequestPhoto ───────────────────────────────────────────────────────

class RequestPhotoSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.SerializerMethodField()
    photo_url        = serializers.SerializerMethodField()
    photo_type_display = serializers.CharField(source="get_photo_type_display")

    class Meta:
        model  = RequestPhoto
        fields = [
            "id",
            "photo_type",
            "photo_type_display",
            "photo_url",
            "uploaded_by_name",
            "created_at",
        ]

    def get_uploaded_by_name(self, obj):
        if obj.uploaded_by:
            return obj.uploaded_by.get_full_name() or obj.uploaded_by.username
        return None

    def get_photo_url(self, obj):
        request = self.context.get("request")
        if obj.photo and request:
            return request.build_absolute_uri(obj.photo.url)
        return obj.photo.url if obj.photo else None


# ─── Driver: TripListSerializer ────────────────────────────────────────────────

class TripListSerializer(serializers.ModelSerializer):
    status_display   = serializers.CharField(source="get_status_display")
    priority_display = serializers.CharField(source="get_priority_display")
    has_open_problem = serializers.SerializerMethodField()
    vehicle_plate    = serializers.SerializerMethodField()
    warehouse_name   = serializers.CharField(source="warehouse.name", default=None)
    cargo_summary    = serializers.SerializerMethodField()
    next_status      = serializers.SerializerMethodField()
    next_status_display = serializers.SerializerMethodField()

    class Meta:
        model  = LogisticsRequest
        fields = [
            "id",
            "request_number",
            "client_name",
            "client_address",
            "client_phone",
            "planned_ship_date",
            "planned_delivery_date",
            "actual_ship_date",
            "status",
            "status_display",
            "priority",
            "priority_display",
            "vehicle_plate",
            "warehouse_name",
            "has_open_problem",
            "cargo_summary",
            "next_status",
            "next_status_display",
        ]

    def get_has_open_problem(self, obj):
        if hasattr(obj, "_prefetched_objects_cache") and "problems" in obj._prefetched_objects_cache:
            return any(
                p.status in (ProblemReport.OPEN, ProblemReport.IN_PROGRESS)
                for p in obj._prefetched_objects_cache["problems"]
            )
        return obj.problems.filter(status__in=[ProblemReport.OPEN, ProblemReport.IN_PROGRESS]).exists()

    def get_vehicle_plate(self, obj):
        return obj.assigned_vehicle.plate_number if obj.assigned_vehicle else None

    def get_cargo_summary(self, obj):
        return f"{obj.cargo_places_count} мест · {obj.cargo_weight_kg} кг"

    def get_next_status(self, obj):
        return DRIVER_STATUS_TRANSITIONS.get(obj.status)

    def get_next_status_display(self, obj):
        ns = DRIVER_STATUS_TRANSITIONS.get(obj.status)
        return STATUS_DISPLAY.get(ns) if ns else None


# ─── Driver: TripDetailSerializer ──────────────────────────────────────────────

class TripDetailSerializer(serializers.ModelSerializer):
    status_display   = serializers.CharField(source="get_status_display")
    priority_display = serializers.CharField(source="get_priority_display")
    cz_status_display = serializers.CharField(source="get_cz_status_display")
    has_open_problem = serializers.SerializerMethodField()
    vehicle_plate    = serializers.SerializerMethodField()
    warehouse_name   = serializers.CharField(source="warehouse.name", default=None)
    cargo_items      = CargoItemSerializer(many=True, read_only=True)
    open_problems    = serializers.SerializerMethodField()
    driver_photos    = serializers.SerializerMethodField()
    allowed_status_transitions = serializers.SerializerMethodField()
    odometer_km      = serializers.SerializerMethodField()

    class Meta:
        model  = LogisticsRequest
        fields = [
            # Идентификация
            "id",
            "request_number",
            "status",
            "status_display",
            "priority",
            "priority_display",
            # Клиент
            "client_name",
            "client_address",
            "client_contact",
            "client_phone",
            "region",
            # Груз
            "cargo_description",
            "cargo_places_count",
            "cargo_weight_kg",
            "cargo_volume_m3",
            "dimensions_text",
            "cargo_items",
            # Склад / транспорт
            "warehouse_name",
            "vehicle_plate",
            # Даты
            "planned_ship_date",
            "actual_ship_date",
            "planned_delivery_date",
            "actual_delivery_date",
            "updated_at",
            # ЧЗ
            "cz_required",
            "cz_status",
            "cz_status_display",
            # Флаги
            "has_open_problem",
            # Вложенные
            "open_problems",
            "driver_photos",
            "odometer_km",
            "allowed_status_transitions",
        ]

    def get_has_open_problem(self, obj):
        return obj.problems.filter(status__in=[ProblemReport.OPEN, ProblemReport.IN_PROGRESS]).exists()

    def get_vehicle_plate(self, obj):
        return obj.assigned_vehicle.plate_number if obj.assigned_vehicle else None

    def get_open_problems(self, obj):
        qs = obj.problems.filter(status__in=[ProblemReport.OPEN, ProblemReport.IN_PROGRESS])
        return ProblemSerializer(qs, many=True).data

    def get_driver_photos(self, obj):
        photos = obj.driver_photos.select_related("uploaded_by").order_by("created_at")
        return RequestPhotoSerializer(photos, many=True, context=self.context).data

    def get_odometer_km(self, obj):
        """Последнее сохранённое показание одометра для этой заявки из истории статусов."""
        entry = obj.status_history.filter(comment__startswith="odometer:").order_by("-created_at").first()
        if entry:
            try:
                return int(entry.comment.split("odometer:")[1].strip())
            except (IndexError, ValueError):
                pass
        # Fallback: одометр у назначенного автомобиля
        if obj.assigned_vehicle:
            return obj.assigned_vehicle.odometer_km
        return None

    def get_allowed_status_transitions(self, obj):
        ns = DRIVER_STATUS_TRANSITIONS.get(obj.status)
        if not ns:
            return []
        return [{
            "status": ns,
            "display": DRIVER_ACTION_DISPLAY.get(ns, ns),
            "requires_odometer": ns in DRIVER_ODOMETER_REQUIRED,
        }]


# ─── Driver: Input serializers ─────────────────────────────────────────────────

class StatusChangeSerializer(serializers.Serializer):
    status  = serializers.CharField()
    comment = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_status(self, value):
        if value not in DRIVER_STATUS_TRANSITIONS.values():
            raise serializers.ValidationError(f"Недопустимый статус: «{value}».")
        return value


class OdometerSerializer(serializers.Serializer):
    odometer_km = serializers.IntegerField(min_value=0)


class BreakdownSerializer(serializers.Serializer):
    description = serializers.CharField(min_length=5)
    request_id  = serializers.IntegerField(required=False, allow_null=True)
    vehicle_id  = serializers.IntegerField(required=False, allow_null=True)


# ─── Notifications ─────────────────────────────────────────────────────────────

class NotificationSerializer(serializers.ModelSerializer):
    request_number = serializers.SerializerMethodField()
    request_id = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ["id", "message", "is_read", "created_at", "request_id", "request_number"]

    def get_request_number(self, obj):
        return obj.request.request_number if obj.request else None

    def get_request_id(self, obj):
        return obj.request_id
