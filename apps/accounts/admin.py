from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Role, User, UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    extra = 0


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Единый Контур", {"fields": ("role", "telegram_chat_id")}),)
    list_display = ("username", "email", "first_name", "last_name", "role", "is_staff")
    list_filter = UserAdmin.list_filter + ("role",)
    inlines = (UserProfileInline,)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "phone", "telegram_id", "default_vehicle", "is_active")
    list_filter = ("role", "is_active")
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "user__email",
        "phone",
        "telegram_id",
        "default_vehicle__plate_number",
    )
    list_select_related = ("user", "default_vehicle")


admin.site.register(Role)
