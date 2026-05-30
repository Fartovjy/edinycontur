from django.urls import path

from . import views

app_name = "checklists"

urlpatterns = [
    path("checklist-item/<int:item_pk>/toggle/", views.checklist_item_toggle, name="item_toggle"),
]
