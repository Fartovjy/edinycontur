from django.contrib import admin

from .models import ProblemReport


@admin.register(ProblemReport)
class ProblemReportAdmin(admin.ModelAdmin):
    list_display = ("request", "problem_type", "status", "responsible_user", "created_by", "created_at", "resolved_at")
    list_filter = ("problem_type", "status", "responsible_user", "created_at", "resolved_at")
    search_fields = (
        "request__request_number",
        "request__client_name",
        "description",
        "resolution_comment",
        "responsible_user__username",
        "created_by__username",
    )
    list_select_related = ("request", "responsible_user", "created_by")
    readonly_fields = ("created_at", "resolved_at")
