from django.contrib import admin
from .models import ChecklistTemplate, ChecklistTemplateItem, RequestChecklistItem

class ChecklistTemplateItemInline(admin.TabularInline):
    model = ChecklistTemplateItem
    extra = 1
    fields = ("order", "text", "is_active")
    ordering = ("order",)

@admin.register(ChecklistTemplate)
class ChecklistTemplateAdmin(admin.ModelAdmin):
    list_display = ("role", "name", "is_active", "updated_at")
    list_filter = ("is_active",)
    inlines = [ChecklistTemplateItemInline]

@admin.register(RequestChecklistItem)
class RequestChecklistItemAdmin(admin.ModelAdmin):
    list_display = ("request", "role", "text", "is_done", "checked_by", "checked_at")
    list_filter = ("role", "is_done")
    search_fields = ("request__request_number", "text")
    readonly_fields = ("checked_at", "checked_by")