from django.urls import path

from . import views

app_name = "api"

urlpatterns = [
    # Auth
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    # Me
    path("me/", views.MeView.as_view(), name="me"),
    # Devices (FCM)
    path("devices/register/", views.DeviceRegisterView.as_view(), name="device_register"),
    path("devices/<str:fcm_token>/", views.DeviceUnregisterView.as_view(), name="device_unregister"),
    # Requests
    path("requests/", views.RequestListView.as_view(), name="request_list"),
    path("requests/<int:pk>/", views.RequestDetailView.as_view(), name="request_detail"),
    # Notifications
    path("notifications/", views.NotificationListView.as_view(), name="notification_list"),
    path("notifications/<int:pk>/read/", views.NotificationReadView.as_view(), name="notification_read"),
]
