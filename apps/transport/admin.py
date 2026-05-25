from django.contrib import admin

from .models import Driver, Vehicle


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("plate_number", "name", "vehicle_type", "color", "year", "max_weight_kg", "max_volume_m3", "is_active")
    list_filter = ("vehicle_type", "is_active")
    search_fields = ("plate_number", "name", "vehicle_type")
    fieldsets = (
        (None, {"fields": ("plate_number", "name", "vehicle_type", "is_active")}),
        ("Характеристики", {"fields": ("max_weight_kg", "max_volume_m3", "color", "year")}),
        ("Медиа и заметки", {"fields": ("photo", "notes")}),
    )


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "telegram_chat_id", "user", "is_active")
    list_filter = ("is_active",)
    search_fields = ("full_name", "phone", "telegram_chat_id", "user__username", "user__first_name", "user__last_name")
    list_select_related = ("user",)
