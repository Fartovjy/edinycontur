from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import resolve_url


class LoginRequiredMiddleware:
    """Require authentication for system pages by default."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated or self._is_public_path(request.path_info):
            return self.get_response(request)

        return redirect_to_login(request.get_full_path(), resolve_url(settings.LOGIN_URL))

    def _is_public_path(self, path):
        public_prefixes = (
            resolve_url(settings.LOGIN_URL),
            resolve_url(settings.LOGOUT_REDIRECT_URL),
            "/admin/",
            settings.STATIC_URL,
            settings.MEDIA_URL,
            "/api/",  # REST API использует TokenAuthentication, своя проверка
        )
        return any(path.startswith(prefix) for prefix in public_prefixes if prefix)
