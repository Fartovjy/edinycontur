from django.contrib import admin
from django.utils.html import format_html

from .models import DeviceToken, RequestPhoto


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "platform", "last_seen_at", "created_at", "token_short")
    list_filter = ("platform",)
    search_fields = ("user__username", "user__first_name", "user__last_name", "fcm_token")
    readonly_fields = ("fcm_token", "last_seen_at", "created_at")
    ordering = ("-last_seen_at",)

    def token_short(self, obj):
        return f"…{obj.fcm_token[-16:]}"
    token_short.short_description = "Токен (последние 16)"


@admin.register(RequestPhoto)
class RequestPhotoAdmin(admin.ModelAdmin):
    list_display  = ("request", "photo_type", "uploaded_by", "created_at", "thumb")
    list_filter   = ("photo_type",)
    search_fields = ("request__request_number", "uploaded_by__username")
    readonly_fields = ("created_at", "thumb")
    ordering      = ("-created_at",)

    def thumb(self, obj):
        if obj.photo:
            return format_html('<img src="{}" style="height:48px;border-radius:4px">', obj.photo.url)
        return "—"
    thumb.short_description = "Превью"
