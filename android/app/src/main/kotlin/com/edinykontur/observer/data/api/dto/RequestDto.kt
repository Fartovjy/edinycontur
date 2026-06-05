package com.edinykontur.observer.data.api.dto

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class RequestListResponse(
    val results: List<RequestListItemDto>,
    @Json(name = "server_time") val serverTime: String,
    val count: Int,
)

@JsonClass(generateAdapter = true)
data class RequestListItemDto(
    val id: Int,
    @Json(name = "request_number") val requestNumber: String,
    @Json(name = "client_name") val clientName: String,
    @Json(name = "planned_delivery_date") val plannedDeliveryDate: String?,
    val status: String,
    @Json(name = "status_display") val statusDisplay: String,
    val priority: String,
    @Json(name = "priority_display") val priorityDisplay: String,
    @Json(name = "has_open_problem") val hasOpenProblem: Boolean,
    @Json(name = "updated_at") val updatedAt: String,
)

@JsonClass(generateAdapter = true)
data class RequestDetailDto(
    val id: Int,
    @Json(name = "request_number") val requestNumber: String,
    val status: String,
    @Json(name = "status_display") val statusDisplay: String,
    val priority: String,
    @Json(name = "priority_display") val priorityDisplay: String,
    // Клиент
    @Json(name = "client_name") val clientName: String,
    @Json(name = "client_address") val clientAddress: String,
    @Json(name = "client_contact") val clientContact: String,
    @Json(name = "client_phone") val clientPhone: String,
    val region: String,
    // Груз
    @Json(name = "cargo_description") val cargoDescription: String,
    @Json(name = "cargo_places_count") val cargoPlacesCount: Int,
    @Json(name = "cargo_weight_kg") val cargoWeightKg: String,
    @Json(name = "cargo_volume_m3") val cargoVolumeM3: String,
    @Json(name = "dimensions_text") val dimensionsText: String,
    // Склад / транспорт
    @Json(name = "warehouse_name") val warehouseName: String?,
    @Json(name = "vehicle_plate") val vehiclePlate: String?,
    @Json(name = "driver_name") val driverName: String?,
    // Даты
    @Json(name = "supply_eta_date") val supplyEtaDate: String?,
    @Json(name = "warehouse_arrival_date") val warehouseArrivalDate: String?,
    @Json(name = "planned_ship_date") val plannedShipDate: String?,
    @Json(name = "actual_ship_date") val actualShipDate: String?,
    @Json(name = "planned_delivery_date") val plannedDeliveryDate: String?,
    @Json(name = "actual_delivery_date") val actualDeliveryDate: String?,
    @Json(name = "created_at") val createdAt: String,
    @Json(name = "updated_at") val updatedAt: String,
    // ЧЗ
    @Json(name = "cz_required") val czRequired: Boolean,
    @Json(name = "cz_status") val czStatus: String,
    @Json(name = "cz_status_display") val czStatusDisplay: String,
    @Json(name = "cz_comment") val czComment: String,
    // Флаги
    @Json(name = "has_open_problem") val hasOpenProblem: Boolean,
    // Вложенные
    @Json(name = "status_history") val statusHistory: List<StatusHistoryDto>,
    @Json(name = "open_problems") val openProblems: List<ProblemDto>,
    @Json(name = "cargo_items") val cargoItems: List<CargoItemDto>,
)

@JsonClass(generateAdapter = true)
data class StatusHistoryDto(
    val id: Int,
    @Json(name = "old_status") val oldStatus: String,
    @Json(name = "old_status_display") val oldStatusDisplay: String,
    @Json(name = "new_status") val newStatus: String,
    @Json(name = "new_status_display") val newStatusDisplay: String,
    @Json(name = "changed_by_name") val changedByName: String?,
    val comment: String,
    @Json(name = "created_at") val createdAt: String,
)

@JsonClass(generateAdapter = true)
data class ProblemDto(
    val id: Int,
    @Json(name = "problem_type") val problemType: String,
    @Json(name = "problem_type_display") val problemTypeDisplay: String,
    val description: String,
    val status: String,
    @Json(name = "status_display") val statusDisplay: String,
    @Json(name = "created_at") val createdAt: String,
)

@JsonClass(generateAdapter = true)
data class CargoItemDto(
    val id: Int,
    val name: String,
    val qty: String,
    @Json(name = "needs_cz") val needsCz: Boolean,
    @Json(name = "supply_date") val supplyDate: String?,
    @Json(name = "is_stocked") val isStocked: Boolean,
)
