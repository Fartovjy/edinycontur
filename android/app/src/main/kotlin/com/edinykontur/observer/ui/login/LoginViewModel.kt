package com.edinykontur.observer.ui.login

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.edinykontur.observer.data.prefs.TokenStorage
import com.edinykontur.observer.data.repository.AuthRepository
import com.edinykontur.observer.data.repository.AuthResult
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class LoginUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    val isLoggedIn: Boolean = false,
)

@HiltViewModel
class LoginViewModel @Inject constructor(
    private val authRepository: AuthRepository,
    private val tokenStorage: TokenStorage,
) : ViewModel() {

    private val _uiState = MutableStateFlow(LoginUiState())
    val uiState: StateFlow<LoginUiState> = _uiState

    init {
        // Если уже есть токен — сразу переходим
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
                is AuthResult.Success -> _uiState.value = LoginUiState(isLoggedIn = true)
                is AuthResult.Error   -> _uiState.value = LoginUiState(error = result.message)
            }
        }
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }
}
