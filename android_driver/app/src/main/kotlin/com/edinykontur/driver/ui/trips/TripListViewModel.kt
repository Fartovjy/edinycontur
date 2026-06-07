package com.edinykontur.driver.ui.trips

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.edinykontur.driver.data.api.dto.TripListItem
import com.edinykontur.driver.data.repository.ApiResult
import com.edinykontur.driver.data.repository.AuthRepository
import com.edinykontur.driver.data.repository.TripRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class TripListUiState(
    val isLoading: Boolean = false,
    val error:     String? = null,
    val trips:     List<TripListItem> = emptyList(),
)

@HiltViewModel
class TripListViewModel @Inject constructor(
    private val tripRepository: TripRepository,
    private val authRepository: AuthRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(TripListUiState())
    val uiState: StateFlow<TripListUiState> = _uiState

    init {
        loadTrips()
    }

    fun loadTrips() {
        _uiState.value = _uiState.value.copy(isLoading = true, error = null)
        viewModelScope.launch {
            when (val result = tripRepository.getTrips()) {
                is ApiResult.Success -> _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    trips = result.data.results,
                )
                is ApiResult.Error -> _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = result.message,
                )
            }
        }
    }

    /** Вызывается при ON_RESUME — обновляем список рейсов. */
    fun refresh() {
        loadTrips()
    }

    fun logout(onLoggedOut: () -> Unit) {
        viewModelScope.launch {
            authRepository.logout()
            onLoggedOut()
        }
    }
}
