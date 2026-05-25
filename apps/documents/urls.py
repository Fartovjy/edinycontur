from django.urls import path

from . import views

urlpatterns = [
    path("documents/<int:pk>/download/", views.attachment_download, name="attachment_download"),
]
