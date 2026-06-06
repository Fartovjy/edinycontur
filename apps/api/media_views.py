"""Защищённая отдача медиафайлов через X-Accel-Redirect.

Поддерживает два метода аутентификации:
  - Session (веб-браузер) — проверяет request.user.is_authenticated
  - Token (мобильное API) — проверяет Authorization: Token <key>

Nginx должен иметь location /protected_media/ { internal; alias /var/www/media/; }
"""

import logging

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect, resolve_url
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

logger = logging.getLogger(__name__)


def serve_protected_media(request, file_path):
    """Выдаёт медиафайл только авторизованным пользователям.

    Работает для сессионной (веб) и токенной (API) аутентификации.
    Возвращает X-Accel-Redirect — nginx отдаёт файл самостоятельно.
    """
    # 1. Сессионная аутентификация (веб-браузер)
    if request.user.is_authenticated:
        return _accel_redirect(file_path)

    # 2. Токенная аутентификация (мобильное приложение)
    try:
        result = TokenAuthentication().authenticate(request)
        if result is not None:
            return _accel_redirect(file_path)
    except AuthenticationFailed:
        pass

    # 3. Не авторизован
    # Если похоже на API-запрос (есть Authorization header или XMLHttpRequest) — 403
    if request.headers.get("Authorization") or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return HttpResponse(status=403)

    # Иначе — редирект на страницу входа
    return redirect(resolve_url(settings.LOGIN_URL) + f"?next={request.get_full_path()}")


def _accel_redirect(file_path):
    """Возвращает ответ с X-Accel-Redirect для nginx."""
    response = HttpResponse()
    # Убираем возможный leading slash, чтобы не было двойного слэша
    clean_path = file_path.lstrip("/")
    response["X-Accel-Redirect"] = f"/protected_media/{clean_path}"
    # Content-Type не выставляем — nginx определит по расширению
    del response["Content-Type"]
    return response
