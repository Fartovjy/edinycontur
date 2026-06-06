from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from apps.api.media_views import serve_protected_media


urlpatterns = [
    # Нестандартный URL для Django Admin — снижает вероятность обнаружения сканерами
    path("ek-site-admin/", admin.site.urls),
    path("accounts/login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("apps.accounts.urls")),
    path("", include("apps.documents.urls")),
    path("", include("apps.notifications.urls")),
    path("", include("apps.checklists.urls")),
    path("", include("apps.logistics.urls")),
    path("api/v1/", include("apps.api.urls")),
]

if settings.DEBUG:
    # В DEBUG nginx не участвует — Django отдаёт медиа напрямую
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # В продакшне: отдаём медиа через X-Accel-Redirect с проверкой авторизации.
    # Публичные пути (branding) обрабатываются nginx раньше и сюда не доходят.
    urlpatterns += [
        path("media/<path:file_path>", serve_protected_media, name="serve_media"),
    ]
