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

/** Статусы, считающиеся "завершёнными" (архив). */
private val COMPLETED_STATUSES = setOf("delivered", "closed", "cancelled")

data class RequestListUiState(
    val isLoading: Boolean = false,
    val isRefreshing: Boolean = false,
    val allRequests: List<RequestListItemDto> = emptyList(),
    val error: String? = null,
    /** Если false — показываем только активные (не завершённые). */
    val showCompleted: Boolean = false,
) {
    /** Список с учётом текущего фильтра. */
    val requests: List<RequestListItemDto>
        get() = if (showCompleted) allRequests
                else allRequests.filter { it.status !in COMPLETED_STATUSES }

    val activeCount: Int
        get() = allRequests.count { it.status !in COMPLETED_STATUSES }

    val completedCount: Int
        get() = allRequests.count { it.status in COMPLETED_STATUSES }
}

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

    /** Переключить режим "показать завершённые". */
    fun toggleShowCompleted() {
        _uiState.value = _uiState.value.copy(showCompleted = !_uiState.value.showCompleted)
    }

    private fun load(incremental: Boolean) {
        viewModelScope.launch {
            loadInner(incremental)
        }
    }

    private suspend fun loadInner(incremental: Boolean) {
        when (val result = requestRepository.fetchRequests(incremental)) {
            is ApiResult.Success -> _uiState.value = _uiState.value.copy(
                allRequests = result.data,
                isLoading = false,
                isRefreshing = false,
                error = null,
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
