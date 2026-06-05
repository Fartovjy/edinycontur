package com.edinykontur.observer.ui.detail

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.edinykontur.observer.data.api.dto.RequestDetailDto
import com.edinykontur.observer.data.repository.ApiResult
import com.edinykontur.observer.data.repository.RequestRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class DetailUiState(
    val isLoading: Boolean = true,
    val request: RequestDetailDto? = null,
    val error: String? = null,
)

@HiltViewModel
class DetailViewModel @Inject constructor(
    private val requestRepository: RequestRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(DetailUiState())
    val uiState: StateFlow<DetailUiState> = _uiState

    fun load(requestId: Int) {
        _uiState.value = DetailUiState(isLoading = true)
        viewModelScope.launch {
            when (val result = requestRepository.fetchRequestDetail(requestId)) {
                is ApiResult.Success -> _uiState.value = DetailUiState(request = result.data)
                is ApiResult.Error   -> _uiState.value = DetailUiState(error = result.message)
            }
        }
    }
}
