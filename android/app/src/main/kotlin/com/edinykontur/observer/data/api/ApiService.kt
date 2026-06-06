package com.edinykontur.observer.data.api

import com.edinykontur.observer.data.api.dto.*
import retrofit2.Response
import retrofit2.http.*

interface ApiService {

    // ── Version check (публичный) ─────────────────────────────────────────────
    @GET("api/v1/version/")
    suspend fun getAppVersion(): Response<AppVersionResponse>

    // ── Auth ──────────────────────────────────────────────────────────────────
    @POST("api/v1/auth/login/")
    suspend fun login(@Body body: LoginRequest): Response<LoginResponse>

    @POST("api/v1/auth/logout/")
    suspend fun logout(): Response<Unit>

    // ── Me ────────────────────────────────────────────────────────────────────
    @GET("api/v1/me/")
    suspend fun getMe(): Response<UserDto>

    // ── Devices ───────────────────────────────────────────────────────────────
    @POST("api/v1/devices/register/")
    suspend fun registerDevice(@Body body: DeviceTokenRequest): Response<Map<String, Any>>

    @DELETE("api/v1/devices/{token}/")
    suspend fun unregisterDevice(@Path("token", encoded = true) token: String): Response<Unit>

    // ── Requests ──────────────────────────────────────────────────────────────
    @GET("api/v1/requests/")
    suspend fun getRequests(
        @Query("since") since: String? = null,
    ): Response<RequestListResponse>

    @GET("api/v1/requests/{id}/")
    suspend fun getRequest(@Path("id") id: Int): Response<RequestDetailDto>

    // ── Notifications ─────────────────────────────────────────────────────────
    @GET("api/v1/notifications/")
    suspend fun getNotifications(): Response<NotificationListResponse>

    @POST("api/v1/notifications/{id}/read/")
    suspend fun markNotificationRead(@Path("id") id: Int): Response<Map<String, Any>>
}
