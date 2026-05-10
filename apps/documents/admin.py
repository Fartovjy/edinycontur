from django.contrib import admin

from .models import Attachment


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("request", "file_type", "file", "uploaded_by", "uploaded_at")
    list_filter = ("file_type", "uploaded_by", "uploaded_at")
    search_fields = (
        "request__request_number",
        "request__client_name",
        "description",
        "file",
        "uploaded_by__username",
        "uploaded_by__first_name",
        "uploaded_by__last_name",
    )
    list_select_related = ("request", "uploaded_by")
    readonly_fields = ("uploaded_at",)
