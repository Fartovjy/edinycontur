package com.edinykontur.driver.ui.breakdown

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.edinykontur.driver.data.repository.ApiResult
import com.edinykontur.driver.data.repository.TripRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class BreakdownUiState(
    val isSending: Boolean = false,
    val error:     String? = null,
    val success:   Boolean = false,
)

@HiltViewModel
class BreakdownViewModel @Inject constructor(
    private val tripRepository: TripRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(BreakdownUiState())
    val uiState: StateFlow<BreakdownUiState> = _uiState

    fun send(description: String, requestId: Int? = null) {
        if (description.isBlank()) {
            _uiState.value = _uiState.value.copy(error = "Введите описание проблемы")
            return
        }
        _uiState.value = _uiState.value.copy(isSending = true, error = null)
        viewModelScope.launch {
            when (val result = tripRepository.reportBreakdown(description, requestId)) {
                is ApiResult.Success -> _uiState.value = BreakdownUiState(success = true)
                is ApiResult.Error   -> _uiState.value = BreakdownUiState(error = result.message)
            }
        }
    }
}
