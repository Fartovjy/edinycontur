package com.edinykontur.driver.ui.login

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.edinykontur.driver.data.api.DriverApiService
import com.edinykontur.driver.data.api.dto.DeviceTokenRequest
import com.edinykontur.driver.data.prefs.TokenStorage
import com.edinykontur.driver.data.repository.AuthRepository
import com.edinykontur.driver.data.repository.AuthResult
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class LoginUiState(
    val isLoading:  Boolean = false,
    val error:      String? = null,
    val isLoggedIn: Boolean = false,
)

@HiltViewModel
class LoginViewModel @Inject constructor(
    private val authRepository: AuthRepository,
    private val tokenStorage: TokenStorage,
    private val api: DriverApiService,
) : ViewModel() {

    private val _uiState = MutableStateFlow(LoginUiState())
    val uiState: StateFlow<LoginUiState> = _uiState

    init {
        if (tokenStorage.getToken() != null) {
            _uiState.value = LoginUiState(isLoggedIn = true)
        }
    }

    fun login(username: String, password: String) {
        if (username.isBlank() || password.isBlank()) {
            _uiState.value = _uiState.value.copy(error = "Введите логин и пароль")
            return
        }
        _uiState.value = _uiState.value.copy(isLoading = true, error = null)
        viewModelScope.launch {
            when (val result = authRepository.login(username, password)) {
                is AuthResult.Success -> {
                    _uiState.value = LoginUiState(isLoggedIn = true)
                    registerFcmToken()
                }
                is AuthResult.Error   -> _uiState.value = LoginUiState(error = result.message)
            }
        }
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    /**
     * Регистрирует FCM-токен на сервере после успешного входа.
     *
     * Раскомментируйте после настройки Firebase (google-services.json + build.gradle.kts):
     *   1. Раскомментируйте блок ниже
     *   2. В build.gradle.kts раскомментируйте: google.services plugin + firebase.messaging
     *   3. В AndroidManifest.xml раскомментируйте: DriverMessagingService
     */
    private fun registerFcmToken() {
        com.google.firebase.messaging.FirebaseMessaging.getInstance().token
            .addOnSuccessListener { token ->
                viewModelScope.launch {
                    try {
                        api.registerDevice(DeviceTokenRequest(fcmToken = token))
                    } catch (_: Exception) {}
                }
            }
    }
}
