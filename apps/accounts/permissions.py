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
    ROLE_VIEWER,
    ROLE_WAREHOUSE,
)


REQUEST_EDIT_ROLES = {ROLE_ADMIN, ROLE_OPERATOR, ROLE_SUPPLY, ROLE_TRANSPORT, ROLE_WAREHOUSE, ROLE_DRIVER}
STATUS_CHANGE_ROLES = {ROLE_ADMIN, ROLE_OPERATOR, ROLE_SUPPLY, ROLE_TRANSPORT, ROLE_WAREHOUSE, ROLE_DRIVER}
PROBLEM_CREATE_ROLES = {ROLE_ADMIN, ROLE_MANAGER, ROLE_OPERATOR, ROLE_SUPPLY, ROLE_TRANSPORT, ROLE_WAREHOUSE, ROLE_DRIVER}
TRANSPORT_ASSIGN_ROLES = {ROLE_ADMIN, ROLE_TRANSPORT}


def get_user_role(user):
    """Return the effective role code for an authenticated user."""
    if not user or not user.is_authenticated:
        return None

    if hasattr(user, "profile"):
        return user.profile.role

    return None


def user_has_role(user, roles):
    """Check whether a user has one of the given role codes."""
    if isinstance(roles, str):
        roles = {roles}
    return get_user_role(user) in set(roles)


def role_required(*roles, raise_exception=True):
    """Restrict a view to users with one of the given roles."""
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
    """Return True when the user may edit the request card."""
    if user_has_role(user, ROLE_ADMIN):
        return True
    if user_has_role(user, ROLE_DRIVER):
        return bool(logistics_request and logistics_request.assigned_driver and logistics_request.assigned_driver.user_id == user.id)
    return user_has_role(user, REQUEST_EDIT_ROLES)


def can_change_status(user, logistics_request=None, new_status=None):
    """Return True when the user may move the request through statuses."""
    if user_has_role(user, ROLE_ADMIN):
        return True
    if user_has_role(user, ROLE_DRIVER):
        return bool(logistics_request and logistics_request.assigned_driver and logistics_request.assigned_driver.user_id == user.id)
    return user_has_role(user, STATUS_CHANGE_ROLES)


def can_create_problem(user, logistics_request=None):
    """Return True when the user may create a problem report for the request."""
    if user_has_role(user, {ROLE_ADMIN, ROLE_MANAGER}):
        return True
    if user_has_role(user, ROLE_DRIVER):
        return bool(logistics_request and logistics_request.assigned_driver and logistics_request.assigned_driver.user_id == user.id)
    return user_has_role(user, PROBLEM_CREATE_ROLES)


def can_assign_transport(user, logistics_request=None):
    """Return True when the user may assign vehicle and driver."""
    return user_has_role(user, TRANSPORT_ASSIGN_ROLES)
