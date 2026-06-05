package com.edinykontur.observer.data.api.dto

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class NotificationListResponse(
    val results: List<NotificationDto>,
    val count: Int,
)

@JsonClass(generateAdapter = true)
data class NotificationDto(
    val id: Int,
    val message: String,
    @Json(name = "is_read") val isRead: Boolean,
    @Json(name = "created_at") val createdAt: String,
    @Json(name = "request_id") val requestId: Int?,
    @Json(name = "request_number") val requestNumber: String?,
)
