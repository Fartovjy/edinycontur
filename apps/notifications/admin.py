from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("message", "recipient_role", "request", "is_read", "created_at")
    list_filter = ("recipient_role", "is_read", "created_at")
    search_fields = ("message", "request__request_number", "request__client_name")
    readonly_fields = ("created_at",)
