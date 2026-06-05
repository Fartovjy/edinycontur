package com.edinykontur.driver.data.api.dto

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class LoginRequest(
    val username: String,
    val password: String,
)

@JsonClass(generateAdapter = true)
data class LoginResponse(
    val token: String,
    val user: UserDto,
)

@JsonClass(generateAdapter = true)
data class DeviceTokenRequest(
    @Json(name = "fcm_token") val fcmToken: String,
    val platform: String = "android",
)

@JsonClass(generateAdapter = true)
data class UserDto(
    val id: Int,
    val username: String,
    @Json(name = "first_name") val firstName: String,
    @Json(name = "last_name") val lastName: String,
    @Json(name = "full_name") val fullName: String,
    val email: String,
    val role: String,
    @Json(name = "role_display") val roleDisplay: String,
)
