from django.urls import path

from . import views

app_name = "checklists"

urlpatterns = [
    path("checklist-item/<int:item_pk>/toggle/", views.checklist_item_toggle, name="item_toggle"),
    path("current-tasks/", views.current_tasks, name="current_tasks"),
    path("user-task/create/", views.user_task_create, name="user_task_create"),
    path("user-task/<int:task_pk>/toggle/", views.user_task_toggle, name="user_task_toggle"),
    path("user-task/<int:task_pk>/delete/", views.user_task_delete, name="user_task_delete"),
]
