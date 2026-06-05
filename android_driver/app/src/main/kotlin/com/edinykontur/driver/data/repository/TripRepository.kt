package com.edinykontur.driver.data.repository

import com.edinykontur.driver.data.api.DriverApiService
import com.edinykontur.driver.data.api.dto.*
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File
import javax.inject.Inject
import javax.inject.Singleton

sealed class ApiResult<out T> {
    data class Success<T>(val data: T) : ApiResult<T>()
    data class Error(val message: String) : ApiResult<Nothing>()
}

@Singleton
class TripRepository @Inject constructor(
    private val api: DriverApiService,
) {
    suspend fun getTrips(date: String? = null): ApiResult<TripListResponse> = safeCall {
        val r = api.getTrips(date)
        if (r.isSuccessful) ApiResult.Success(r.body()!!)
        else ApiResult.Error("Ошибка ${r.code()}")
    }

    suspend fun getTripDetail(id: Int): ApiResult<TripDetail> = safeCall {
        val r = api.getTripDetail(id)
        if (r.isSuccessful) ApiResult.Success(r.body()!!)
        else ApiResult.Error("Ошибка ${r.code()}")
    }

    suspend fun updateStatus(id: Int, status: String, comment: String = ""): ApiResult<Unit> = safeCall {
        val r = api.updateStatus(id, StatusChangeRequest(status, comment))
        if (r.isSuccessful) ApiResult.Success(Unit)
        else {
            val err = r.errorBody()?.string() ?: "Ошибка ${r.code()}"
            ApiResult.Error(err)
        }
    }

    suspend fun saveOdometer(id: Int, km: Int): ApiResult<Unit> = safeCall {
        val r = api.saveOdometer(id, OdometerRequest(km))
        if (r.isSuccessful) ApiResult.Success(Unit)
        else ApiResult.Error("Ошибка ${r.code()}")
    }

    suspend fun uploadPhoto(id: Int, file: File, photoType: String): ApiResult<PhotoDto> = safeCall {
        val reqBody  = file.asRequestBody("image/jpeg".toMediaTypeOrNull())
        val part     = MultipartBody.Part.createFormData("file", file.name, reqBody)
        val typePart = photoType.toRequestBody("text/plain".toMediaTypeOrNull())
        val r = api.uploadPhoto(id, part, typePart)
        if (r.isSuccessful) ApiResult.Success(r.body()!!)
        else ApiResult.Error("Ошибка загрузки: ${r.code()}")
    }

    suspend fun reportBreakdown(description: String, requestId: Int? = null): ApiResult<Unit> = safeCall {
        val r = api.reportBreakdown(BreakdownRequest(description, requestId))
        if (r.isSuccessful) ApiResult.Success(Unit)
        else ApiResult.Error("Ошибка ${r.code()}")
    }

    private suspend fun <T> safeCall(block: suspend () -> ApiResult<T>): ApiResult<T> {
        return try {
            block()
        } catch (e: Exception) {
            ApiResult.Error("Нет соединения с сервером.")
        }
    }
}
