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

enum class RequestFilter { ACTIVE, PROBLEMS, ARCHIVE }

private val COMPLETED_STATUSES = setOf("delivered", "closed", "cancelled")
private val PROBLEM_STATUSES   = setOf("problem")

data class RequestListUiState(
    val isLoading: Boolean = false,
    val isRefreshing: Boolean = false,
    val allRequests: List<RequestListItemDto> = emptyList(),
    val error: String? = null,
    val filter: RequestFilter = RequestFilter.ACTIVE,
) {
    val requests: List<RequestListItemDto>
        get() = when (filter) {
            RequestFilter.ACTIVE   -> allRequests.filter { it.status !in COMPLETED_STATUSES }
            RequestFilter.PROBLEMS -> allRequests.filter { it.hasOpenProblem || it.status in PROBLEM_STATUSES }
            RequestFilter.ARCHIVE  -> allRequests.filter { it.status in COMPLETED_STATUSES }
        }

    val activeCount:   Int get() = allRequests.count { it.status !in COMPLETED_STATUSES }
    val problemCount:  Int get() = allRequests.count { it.hasOpenProblem || it.status in PROBLEM_STATUSES }
    val archiveCount:  Int get() = allRequests.count { it.status in COMPLETED_STATUSES }
}

@HiltViewModel
class ListViewModel @Inject constructor(
    private val requestRepository: RequestRepository,
    private val authRepository: AuthRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(RequestListUiState(isLoading = true))
    val uiState: StateFlow<RequestListUiState> = _uiState

    init { load() }

    fun refresh() {
        _uiState.value = _uiState.value.copy(isRefreshing = true, error = null)
        viewModelScope.launch { loadInner(incremental = false) }
    }

    fun setFilter(f: RequestFilter) {
        _uiState.value = _uiState.value.copy(filter = f)
    }

    private fun load() {
        viewModelScope.launch { loadInner(incremental = false) }
    }

    private suspend fun loadInner(incremental: Boolean) {
        when (val result = requestRepository.fetchRequests(incremental)) {
            is ApiResult.Success -> _uiState.value = _uiState.value.copy(
                allRequests  = result.data,
                isLoading    = false,
                isRefreshing = false,
                error        = null,
            )
            is ApiResult.Error -> _uiState.value = _uiState.value.copy(
                isLoading    = false,
                isRefreshing = false,
                error        = result.message,
            )
        }
    }

    fun logout(onDone: () -> Unit) {
        viewModelScope.launch { authRepository.logout(); onDone() }
    }
}
