"""Права доступа для мобильного API."""

from rest_framework.permissions import BasePermission

from apps.accounts.constants import ROLE_DRIVER, ROLE_VIEWER


class IsMobileViewerAuthenticated(BasePermission):
    """
    Разрешает доступ только если:
    - пользователь авторизован (токен);
    - у него есть профиль;
    - у профиля mobile_access_enabled = True;
    - роль профиля == ROLE_VIEWER.

    Администратор (is_superuser) или admin-роль получает доступ без проверки
    mobile_access_enabled — для отладки через curl/Postman.
    """

    message = "Нет доступа к мобильному API. Обратитесь к администратору."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        # Суперпользователь/администратор — полный доступ (для отладки)
        if user.is_superuser:
            return True

        profile = getattr(user, "profile", None)
        if not profile:
            return False

        from apps.accounts.constants import ROLE_ADMIN
        if profile.role == ROLE_ADMIN:
            return True

        # Обычная проверка: наблюдатель с включённым мобильным доступом
        return profile.mobile_access_enabled and profile.role == ROLE_VIEWER


class IsMobileDriverAuthenticated(BasePermission):
    """
    Разрешает доступ только если:
    - пользователь авторизован (токен);
    - у него есть профиль;
    - у профиля mobile_access_enabled = True;
    - роль профиля == ROLE_DRIVER.

    Суперпользователь/admin — полный доступ без ограничений (для отладки).
    """

    message = "Нет доступа к API водителя. Обратитесь к администратору."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if user.is_superuser:
            return True

        profile = getattr(user, "profile", None)
        if not profile:
            return False

        from apps.accounts.constants import ROLE_ADMIN
        if profile.role == ROLE_ADMIN:
            return True

        return profile.mobile_access_enabled and profile.role == ROLE_DRIVER
