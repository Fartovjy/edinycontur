from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from .constants import (
    ROLE_ADMIN,
    ROLE_DRIVER,
    ROLE_MANAGER,
    ROLE_OPERATOR,
    ROLE_SUPPLY,
    ROLE_TRANSPORT,
    ROLE_WAREHOUSE,
)


REQUEST_EDIT_ROLES = {ROLE_ADMIN, ROLE_OPERATOR, ROLE_SUPPLY, ROLE_TRANSPORT, ROLE_WAREHOUSE, ROLE_DRIVER}
STATUS_CHANGE_ROLES = {ROLE_ADMIN, ROLE_MANAGER, ROLE_OPERATOR, ROLE_SUPPLY, ROLE_TRANSPORT, ROLE_WAREHOUSE, ROLE_DRIVER}
PROBLEM_CREATE_ROLES = {ROLE_ADMIN, ROLE_MANAGER, ROLE_OPERATOR, ROLE_SUPPLY, ROLE_TRANSPORT, ROLE_WAREHOUSE, ROLE_DRIVER}
TRANSPORT_ASSIGN_ROLES = {ROLE_ADMIN, ROLE_TRANSPORT}


def get_user_role(user):
    if not user or not user.is_authenticated:
        return None

    if hasattr(user, "profile"):
        return user.profile.role

    role = getattr(user, "role", None)
    return getattr(role, "code", None)


def user_has_role(user, roles):
    if isinstance(roles, str):
        roles = {roles}
    return get_user_role(user) in set(roles)


def role_required(*roles, raise_exception=True):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if user_has_role(request.user, roles):
                return view_func(request, *args, **kwargs)
            if raise_exception:
                raise PermissionDenied
            return redirect_to_login(request.get_full_path())

        return wrapped

    return decorator


def can_edit_request(user, logistics_request=None):
    if user_has_role(user, ROLE_ADMIN):
        return True
    if user_has_role(user, ROLE_DRIVER):
        return bool(logistics_request and logistics_request.assigned_driver and logistics_request.assigned_driver.user_id == user.id)
    return user_has_role(user, REQUEST_EDIT_ROLES)


def can_change_status(user, logistics_request=None, new_status=None):
    if user_has_role(user, ROLE_ADMIN):
        return True
    if user_has_role(user, ROLE_DRIVER):
        return bool(logistics_request and logistics_request.assigned_driver and logistics_request.assigned_driver.user_id == user.id)
    return user_has_role(user, STATUS_CHANGE_ROLES)


def can_create_problem(user, logistics_request=None):
    if user_has_role(user, {ROLE_ADMIN, ROLE_MANAGER}):
        return True
    if user_has_role(user, ROLE_DRIVER):
        return bool(logistics_request and logistics_request.assigned_driver and logistics_request.assigned_driver.user_id == user.id)
    return user_has_role(user, PROBLEM_CREATE_ROLES)


def can_assign_transport(user, logistics_request=None):
    return user_has_role(user, TRANSPORT_ASSIGN_ROLES)
