from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("notifications/unread-count/", views.unread_count, name="unread_count"),
]
