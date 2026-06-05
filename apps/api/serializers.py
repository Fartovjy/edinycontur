"""DRF-сериализаторы для мобильного API."""

from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework.authtoken.models import Token

from apps.logistics.models import (
    CargoItem,
    LogisticsRequest,
    RequestStatusHistory,
)
from apps.notifications.models import Notification
from apps.problems.models import ProblemReport


# ─── Auth ──────────────────────────────────────────────────────────────────────

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(label="Логин")
    password = serializers.CharField(label="Пароль", write_only=True, style={"input_type": "password"})

    def validate(self, data):
        user = authenticate(username=data["username"], password=data["password"])
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
