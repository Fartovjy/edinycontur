package com.edinykontur.driver.data.api.dto

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

// ── Список рейсов ──────────────────────────────────────────────────────────────

@JsonClass(generateAdapter = true)
data class TripListResponse(
    val date: String? = null,
    val results: List<TripListItem>,
    val count: Int,
)

@JsonClass(generateAdapter = true)
data class TripListItem(
    val id: Int,
    @Json(name = "request_number") val requestNumber: String,
    @Json(name = "client_name")    val clientName: String,
    @Json(name = "client_address") val clientAddress: String,
    @Json(name = "client_phone")   val clientPhone: String,
    @Json(name = "planned_ship_date")      val plannedShipDate: String?,
    @Json(name = "planned_delivery_date")  val plannedDeliveryDate: String?,
    @Json(name = "actual_ship_date")       val actualShipDate: String?,
    val status: String,
    @Json(name = "status_display")  val statusDisplay: String,
    val priority: String,
    @Json(name = "priority_display") val priorityDisplay: String,
    @Json(name = "vehicle_plate")   val vehiclePlate: String?,
    @Json(name = "warehouse_name")  val warehouseName: String?,
    @Json(name = "has_open_problem") val hasOpenProblem: Boolean,
    @Json(name = "cargo_summary")   val cargoSummary: String,
    @Json(name = "next_status")         val nextStatus: String?,
    @Json(name = "next_status_display") val nextStatusDisplay: String?,
)

// ── Детальная карточка рейса ───────────────────────────────────────────────────

@JsonClass(generateAdapter = true)
data class TripDetail(
    val id: Int,
    @Json(name = "request_number") val requestNumber: String,
    val status: String,
    @Json(name = "status_display")  val statusDisplay: String,
    val priority: String,
    @Json(name = "priority_display") val priorityDisplay: String,
    // Клиент
    @Json(name = "client_name")    val clientName: String,
    @Json(name = "client_address") val clientAddress: String,
    @Json(name = "client_contact") val clientContact: String,
    @Json(name = "client_phone")   val clientPhone: String,
    val region: String,
    // Груз
    @Json(name = "cargo_description")  val cargoDescription: String,
    @Json(name = "cargo_places_count") val cargoPlacesCount: Int,
    @Json(name = "cargo_weight_kg")    val cargoWeightKg: String,
    @Json(name = "cargo_volume_m3")    val cargoVolumeM3: String,
    @Json(name = "dimensions_text")    val dimensionsText: String,
    @Json(name = "cargo_items")        val cargoItems: List<CargoItemDto>,
    // Транспорт / склад
    @Json(name = "warehouse_name") val warehouseName: String?,
    @Json(name = "vehicle_plate")  val vehiclePlate: String?,
    // Даты
    @Json(name = "planned_ship_date")     val plannedShipDate: String?,
    @Json(name = "actual_ship_date")      val actualShipDate: String?,
    @Json(name = "planned_delivery_date") val plannedDeliveryDate: String?,
    @Json(name = "actual_delivery_date")  val actualDeliveryDate: String?,
    @Json(name = "updated_at")            val updatedAt: String,
    // ЧЗ
    @Json(name = "cz_required") val czRequired: Boolean,
    @Json(name = "cz_status")   val czStatus: String,
    @Json(name = "cz_status_display") val czStatusDisplay: String,
    // Флаги
    @Json(name = "has_open_problem") val hasOpenProblem: Boolean,
    // Вложенные
    @Json(name = "open_problems")  val openProblems: List<ProblemDto>,
    @Json(name = "driver_photos")  val driverPhotos: List<PhotoDto>,
    @Json(name = "odometer_km")    val odometerKm: Int?,
    @Json(name = "allowed_status_transitions") val allowedStatusTransitions: List<StatusTransitionDto>,
)

@JsonClass(generateAdapter = true)
data class CargoItemDto(
    val id: Int,
    val name: String,
    val qty: String,
    @Json(name = "needs_cz")    val needsCz: Boolean,
    @Json(name = "supply_date") val supplyDate: String?,
    @Json(name = "is_stocked")  val isStocked: Boolean,
)

@JsonClass(generateAdapter = true)
data class ProblemDto(
    val id: Int,
    @Json(name = "problem_type")         val problemType: String,
    @Json(name = "problem_type_display") val problemTypeDisplay: String,
    val description: String,
    val status: String,
    @Json(name = "status_display") val statusDisplay: String,
    @Json(name = "created_at")     val createdAt: String,
)

@JsonClass(generateAdapter = true)
data class PhotoDto(
    val id: Int,
    @Json(name = "photo_type")         val photoType: String,
    @Json(name = "photo_type_display") val photoTypeDisplay: String,
    @Json(name = "photo_url")          val photoUrl: String?,
    @Json(name = "uploaded_by_name")   val uploadedByName: String?,
    @Json(name = "created_at")         val createdAt: String,
)

@JsonClass(generateAdapter = true)
data class StatusTransitionDto(
    val status: String,
    val display: String,
)

// ── Входящие данные для запросов ───────────────────────────────────────────────

@JsonClass(generateAdapter = true)
data class StatusChangeRequest(
    val status: String,
    val comment: String = "",
)

@JsonClass(generateAdapter = true)
data class OdometerRequest(
    @Json(name = "odometer_km") val odometerKm: Int,
)

@JsonClass(generateAdapter = true)
data class BreakdownRequest(
    val description: String,
    @Json(name = "request_id") val requestId: Int? = null,
)
