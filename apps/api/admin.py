from django.contrib import admin

from .models import DeviceToken


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
