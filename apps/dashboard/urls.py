from django.urls import path

from .views import manager_dashboard

urlpatterns = [
    path("dashboard/", manager_dashboard, name="manager_dashboard"),
]
