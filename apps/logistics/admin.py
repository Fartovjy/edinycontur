from django.contrib import admin

from .models import ArchivistSettings, Client, LogisticsRequest, RequestStatusHistory, Warehouse


class RequestStatusHistoryInline(admin.TabularInline):
    model = RequestStatusHistory
    extra = 0
    can_delete = False
    readonly_fields = ("old_status", "new_status", "changed_by", "comment", "created_at")
    fields = ("created_at", "old_status", "new_status", "changed_by", "comment")
    ordering = ("-created_at",)

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(LogisticsRequest)
class LogisticsRequestAdmin(admin.ModelAdmin):
    list_display = (
        "request_number",
        "client_name",
        "region",
        "status",
        "priority",
        "warehouse",
        "assigned_driver",
        "assigned_vehicle",
        "planned_ship_date",
        "planned_delivery_date",
        "cz_required",
        "cz_checked",
        "cz_problem",
        "is_archived",
        "updated_at",
    )
    list_filter = (
        "status",
        "priority",
        "region",
        "warehouse",
        "assigned_driver",
        "assigned_vehicle",
        "cz_required",
        "cz_checked",
        "cz_problem",
        "is_archived",
        "created_at",
        "updated_at",
        "planned_ship_date",
        "planned_delivery_date",
    )
    search_fields = (
        "request_number",
        "client_name",
        "client_address",
        "client_contact",
        "cargo_description",
        "region",
        "assigned_driver__full_name",
        "assigned_vehicle__plate_number",
    )
    list_select_related = ("warehouse", "assigned_driver", "assigned_vehicle", "created_by")
    readonly_fields = ("created_at", "updated_at")
    inlines = (RequestStatusHistoryInline,)
    fieldsets = (
        (
            "Основное",
            {
                "fields": (
                    "request_number",
                    "status",
                    "priority",
                    "warehouse",
                )
            },
        ),
        (
            "Клиент",
            {
                "fields": (
                    "client_name",
                    "client_address",
                    "client_contact",
                    "region",
                )
            },
        ),
        (
            "Груз",
            {
                "fields": (
                    "cargo_description",
                    "cargo_places_count",
                    "cargo_weight_kg",
                    "cargo_volume_m3",
                    "dimensions_text",
                )
            },
        ),
        (
            "Даты",
            {
                "fields": (
                    "supply_eta_date",
                    "warehouse_arrival_date",
                    "planned_ship_date",
                    "actual_ship_date",
                    "planned_delivery_date",
                    "actual_delivery_date",
                )
            },
        ),
        (
            "Честный Знак",
            {
                "fields": (
                    "cz_required",
                    "cz_checked",
                    "cz_status",
                    "cz_comment",
                    "cz_problem",
                )
            },
        ),
        (
            "Транспорт",
            {
                "fields": (
                    "assigned_vehicle",
                    "assigned_driver",
                )
            },
        ),
        (
            "Служебное",
            {
                "fields": (
                    "created_by",
                    "created_at",
                    "updated_at",
                    "is_archived",
                )
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        old_status = None
        if change and obj.pk:
            old_status = (
                LogisticsRequest.objects.filter(pk=obj.pk)
                .values_list("status", flat=True)
                .first()
            )

        super().save_model(request, obj, form, change)

        if old_status and old_status != obj.status:
            RequestStatusHistory.objects.create(
                request=obj,
                old_status=old_status,
                new_status=obj.status,
                changed_by=request.user,
                comment="Статус изменён через админку",
            )


@admin.register(RequestStatusHistory)
class RequestStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("request", "old_status", "new_status", "changed_by", "created_at", "comment")
    list_filter = ("old_status", "new_status", "changed_by", "created_at")
    search_fields = (
        "request__request_number",
        "request__client_name",
        "changed_by__username",
        "changed_by__first_name",
        "changed_by__last_name",
        "comment",
    )
    list_select_related = ("request", "changed_by")
    readonly_fields = ("request", "old_status", "new_status", "changed_by", "comment", "created_at")


admin.site.register(Client)
admin.site.register(Warehouse)


@admin.register(ArchivistSettings)
class ArchivistSettingsAdmin(admin.ModelAdmin):
    fields = ("retention_days", "updated_at")
    readonly_fields = ("updated_at",)
    list_display = ("retention_days", "updated_at")

    def has_add_permission(self, request):
        return not ArchivistSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
