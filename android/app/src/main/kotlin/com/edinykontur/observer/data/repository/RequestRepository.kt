package com.edinykontur.observer.data.repository

import com.edinykontur.observer.data.api.ApiService
import com.edinykontur.observer.data.api.dto.RequestDetailDto
import com.edinykontur.observer.data.api.dto.RequestListItemDto
import com.edinykontur.observer.data.prefs.TokenStorage
import javax.inject.Inject
import javax.inject.Singleton

sealed class ApiResult<out T> {
    data class Success<T>(val data: T) : ApiResult<T>()
    data class Error(val message: String) : ApiResult<Nothing>()
}

@Singleton
class RequestRepository @Inject constructor(
    private val api: ApiService,
    private val tokenStorage: TokenStorage,
) {
    /**
     * Загрузить список заявок.
     * @param incremental если true — передаём lastSyncAt для инкрементального обновления
     */
    suspend fun fetchRequests(incremental: Boolean = false): ApiResult<List<RequestListItemDto>> {
        return try {
            val since = if (incremental) tokenStorage.getLastSyncAt() else null
            val response = api.getRequests(since)
            if (response.isSuccessful) {
                val body = response.body()!!
                tokenStorage.saveLastSyncAt(body.serverTime)
                ApiResult.Success(body.results)
            } else {
                ApiResult.Error("Ошибка ${response.code()}")
            }
        } catch (e: Exception) {
            ApiResult.Error(e.message ?: "Нет подключения")
        }
    }

    suspend fun fetchRequestDetail(id: Int): ApiResult<RequestDetailDto> {
        return try {
            val response = api.getRequest(id)
            if (response.isSuccessful) {
                ApiResult.Success(response.body()!!)
            } else {
                ApiResult.Error("Ошибка ${response.code()}")
            }
        } catch (e: Exception) {
            ApiResult.Error(e.message ?: "Нет подключения")
        }
    }
}
