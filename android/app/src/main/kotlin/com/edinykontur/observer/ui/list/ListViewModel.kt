package com.edinykontur.observer.ui.list

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.edinykontur.observer.data.api.dto.RequestListItemDto
import com.edinykontur.observer.data.repository.ApiResult
import com.edinykontur.observer.data.repository.AuthRepository
import com.edinykontur.observer.data.repository.RequestRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class RequestListUiState(
    val isLoading: Boolean = false,
    val isRefreshing: Boolean = false,
    val requests: List<RequestListItemDto> = emptyList(),
    val error: String? = null,
)

@HiltViewModel
class ListViewModel @Inject constructor(
    private val requestRepository: RequestRepository,
    private val authRepository: AuthRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(RequestListUiState(isLoading = true))
    val uiState: StateFlow<RequestListUiState> = _uiState

    init {
        load(incremental = false)
    }

    fun refresh() {
        _uiState.value = _uiState.value.copy(isRefreshing = true, error = null)
        viewModelScope.launch {
            loadInner(incremental = false)
        }
    }

    private fun load(incremental: Boolean) {
        viewModelScope.launch {
            loadInner(incremental)
        }
    }

    private suspend fun loadInner(incremental: Boolean) {
        when (val result = requestRepository.fetchRequests(incremental)) {
            is ApiResult.Success -> _uiState.value = RequestListUiState(
                requests = result.data,
                isLoading = false,
                isRefreshing = false,
            )
            is ApiResult.Error   -> _uiState.value = _uiState.value.copy(
                isLoading = false,
                isRefreshing = false,
                error = result.message,
            )
        }
    }

    fun logout(onDone: () -> Unit) {
        viewModelScope.launch {
            authRepository.logout()
            onDone()
        }
    }
}
