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
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import javax.inject.Inject

data class TripListUiState(
    val isLoading:  Boolean = false,
    val error:      String? = null,
    val trips:      List<TripListItem> = emptyList(),
    val selectedDate: LocalDate = LocalDate.now(),
)

@HiltViewModel
class TripListViewModel @Inject constructor(
    private val tripRepository: TripRepository,
    private val authRepository: AuthRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(TripListUiState())
    val uiState: StateFlow<TripListUiState> = _uiState

    private val dateFormatter = DateTimeFormatter.ofPattern("yyyy-MM-dd")

    init {
        loadTrips()
    }

    fun loadTrips(date: LocalDate = _uiState.value.selectedDate) {
        _uiState.value = _uiState.value.copy(isLoading = true, error = null, selectedDate = date)
        viewModelScope.launch {
            when (val result = tripRepository.getTrips(date.format(dateFormatter))) {
                is ApiResult.Success -> _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    trips = result.data.results,
                )
                is ApiResult.Error   -> _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = result.message,
                )
            }
        }
    }

    fun goToPreviousDay() {
        loadTrips(_uiState.value.selectedDate.minusDays(1))
    }

    fun goToNextDay() {
        loadTrips(_uiState.value.selectedDate.plusDays(1))
    }

    fun goToToday() {
        loadTrips(LocalDate.now())
    }

    fun logout(onLoggedOut: () -> Unit) {
        viewModelScope.launch {
            authRepository.logout()
            onLoggedOut()
        }
    }
}
