from django.urls import path

from . import views

app_name = "api"

urlpatterns = [
    # Version check (публичный)
    path("version/", views.AppVersionView.as_view(), name="app_version"),
    # Auth
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    # Me
    path("me/", views.MeView.as_view(), name="me"),
    # Devices (FCM)
    path("devices/register/", views.DeviceRegisterView.as_view(), name="device_register"),
    path("devices/<str:fcm_token>/", views.DeviceUnregisterView.as_view(), name="device_unregister"),
    # Requests (наблюдатель)
    path("requests/", views.RequestListView.as_view(), name="request_list"),
    path("requests/<int:pk>/", views.RequestDetailView.as_view(), name="request_detail"),
    # Notifications
    path("notifications/", views.NotificationListView.as_view(), name="notification_list"),
    path("notifications/<int:pk>/read/", views.NotificationReadView.as_view(), name="notification_read"),
    # ── Driver API ─────────────────────────────────────────────────────────────
    path("driver/trips/",                          views.DriverTripListView.as_view(),    name="driver_trip_list"),
    path("driver/trips/<int:pk>/",                 views.DriverTripDetailView.as_view(),  name="driver_trip_detail"),
    path("driver/trips/<int:pk>/status/",          views.DriverTripStatusView.as_view(),  name="driver_trip_status"),
    path("driver/trips/<int:pk>/odometer/",        views.DriverTripOdometerView.as_view(), name="driver_trip_odometer"),
    path("driver/trips/<int:pk>/photos/",          views.DriverTripPhotosView.as_view(),  name="driver_trip_photos"),
    path("driver/breakdown/",                      views.DriverBreakdownView.as_view(),   name="driver_breakdown"),
]
