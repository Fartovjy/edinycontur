package com.edinykontur.driver.data.api

import com.edinykontur.driver.data.api.dto.*
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.Response
import retrofit2.http.*

interface DriverApiService {

    // ── Auth ──────────────────────────────────────────────────────────────────
    @POST("api/v1/auth/login/")
    suspend fun login(@Body body: LoginRequest): Response<LoginResponse>

    @POST("api/v1/auth/logout/")
    suspend fun logout(): Response<Unit>

    // ── Driver: Trips ─────────────────────────────────────────────────────────
    @GET("api/v1/driver/trips/")
    suspend fun getTrips(
        @Query("date") date: String? = null,
    ): Response<TripListResponse>

    @GET("api/v1/driver/trips/{id}/")
    suspend fun getTripDetail(@Path("id") id: Int): Response<TripDetail>

    // ── Driver: Status ────────────────────────────────────────────────────────
    @POST("api/v1/driver/trips/{id}/status/")
    suspend fun updateStatus(
        @Path("id") id: Int,
        @Body body: StatusChangeRequest,
    ): Response<Map<String, Any>>

    // ── Driver: Odometer ─────────────────────────────────────────────────────
    @POST("api/v1/driver/trips/{id}/odometer/")
    suspend fun saveOdometer(
        @Path("id") id: Int,
        @Body body: OdometerRequest,
    ): Response<Map<String, Any>>

    // ── Driver: Photos ────────────────────────────────────────────────────────
    @GET("api/v1/driver/trips/{id}/photos/")
    suspend fun getPhotos(@Path("id") id: Int): Response<Map<String, Any>>

    @Multipart
    @POST("api/v1/driver/trips/{id}/photos/")
    suspend fun uploadPhoto(
        @Path("id") id: Int,
        @Part file: MultipartBody.Part,
        @Part("photo_type") photoType: RequestBody,
    ): Response<PhotoDto>

    // ── Driver: Breakdown ─────────────────────────────────────────────────────
    @POST("api/v1/driver/breakdown/")
    suspend fun reportBreakdown(@Body body: BreakdownRequest): Response<Map<String, Any>>
}
