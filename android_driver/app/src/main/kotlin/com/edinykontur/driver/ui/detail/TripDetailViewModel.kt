package com.edinykontur.driver.ui.detail

import android.content.Context
import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.edinykontur.driver.data.api.dto.TripDetail
import com.edinykontur.driver.data.repository.ApiResult
import com.edinykontur.driver.data.repository.TripRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import java.io.File
import javax.inject.Inject

data class TripDetailUiState(
    val isLoading:       Boolean   = true,
    val error:           String?   = null,
    val trip:            TripDetail? = null,
    // Actions
    val statusUpdating:  Boolean   = false,
    val statusSuccess:   String?   = null,
    val odometerSaving:  Boolean   = false,
    val odometerSuccess: Boolean   = false,
    val photoUploading:  Boolean   = false,
    val photoSuccess:    Boolean   = false,
    val actionError:     String?   = null,
)

@HiltViewModel
class TripDetailViewModel @Inject constructor(
    private val tripRepository: TripRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(TripDetailUiState())
    val uiState: StateFlow<TripDetailUiState> = _uiState

    fun load(tripId: Int) {
        _uiState.value = _uiState.value.copy(isLoading = true, error = null)
        viewModelScope.launch {
            when (val result = tripRepository.getTripDetail(tripId)) {
                is ApiResult.Success -> _uiState.value = _uiState.value.copy(
                    isLoading = false, trip = result.data)
                is ApiResult.Error   -> _uiState.value = _uiState.value.copy(
                    isLoading = false, error = result.message)
            }
        }
    }

    fun updateStatus(tripId: Int, status: String, comment: String = "") {
        _uiState.value = _uiState.value.copy(statusUpdating = true, actionError = null)
        viewModelScope.launch {
            when (val result = tripRepository.updateStatus(tripId, status, comment)) {
                is ApiResult.Success -> {
                    _uiState.value = _uiState.value.copy(statusUpdating = false, statusSuccess = status)
                    load(tripId)
                }
                is ApiResult.Error -> _uiState.value = _uiState.value.copy(
                    statusUpdating = false, actionError = result.message)
            }
        }
    }

    fun saveOdometer(tripId: Int, km: Int) {
        _uiState.value = _uiState.value.copy(odometerSaving = true, actionError = null)
        viewModelScope.launch {
            when (val result = tripRepository.saveOdometer(tripId, km)) {
                is ApiResult.Success -> _uiState.value = _uiState.value.copy(
                    odometerSaving = false, odometerSuccess = true)
                is ApiResult.Error   -> _uiState.value = _uiState.value.copy(
                    odometerSaving = false, actionError = result.message)
            }
        }
    }

    fun uploadPhoto(context: Context, tripId: Int, uri: Uri, photoType: String) {
        _uiState.value = _uiState.value.copy(photoUploading = true, actionError = null)
        viewModelScope.launch {
            val file = uriToTempFile(context, uri) ?: run {
                _uiState.value = _uiState.value.copy(
                    photoUploading = false, actionError = "Не удалось получить файл")
                return@launch
            }
            when (val result = tripRepository.uploadPhoto(tripId, file, photoType)) {
                is ApiResult.Success -> {
                    file.delete()
                    _uiState.value = _uiState.value.copy(
                        photoUploading = false, photoSuccess = true)
                    load(tripId) // перезагрузить список фото
                }
                is ApiResult.Error -> {
                    file.delete()
                    _uiState.value = _uiState.value.copy(
                        photoUploading = false, actionError = result.message)
                }
            }
        }
    }

    fun clearActionFeedback() {
        _uiState.value = _uiState.value.copy(
            statusSuccess = null,
            odometerSuccess = false,
            photoSuccess = false,
            actionError = null,
        )
    }

    private fun uriToTempFile(context: Context, uri: Uri): File? {
        return try {
            val stream = context.contentResolver.openInputStream(uri) ?: return null
            val tmp = File.createTempFile("photo_", ".jpg", context.cacheDir)
            tmp.outputStream().use { out -> stream.copyTo(out) }
            stream.close()
            tmp
        } catch (e: Exception) {
            null
        }
    }
}
