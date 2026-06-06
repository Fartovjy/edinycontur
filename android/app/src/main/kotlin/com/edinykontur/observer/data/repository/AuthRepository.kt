package com.edinykontur.observer.data.repository

import com.edinykontur.observer.data.api.ApiService
import com.edinykontur.observer.data.api.dto.DeviceTokenRequest
import com.edinykontur.observer.data.api.dto.LoginRequest
import com.edinykontur.observer.data.api.dto.LoginResponse
import com.edinykontur.observer.data.prefs.TokenStorage
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.tasks.await
import kotlinx.coroutines.withContext
import javax.inject.Inject
import javax.inject.Singleton

sealed class AuthResult {
    data class Success(val response: LoginResponse) : AuthResult()
    data class Error(val message: String) : AuthResult()
}

@Singleton
class AuthRepository @Inject constructor(
    private val api: ApiService,
    private val tokenStorage: TokenStorage,
) {
    suspend fun login(username: String, password: String): AuthResult {
        return try {
            val response = api.login(LoginRequest(username, password))
            if (response.isSuccessful) {
                val body = response.body()!!
                tokenStorage.saveToken(body.token)
                // После каждого логина явно регистрируем текущий FCM-токен.
                // onNewToken() вызывается только при смене токена Firebase,
                // а не при смене аккаунта — поэтому регистрируем вручную.
                registerFcmToken()
                AuthResult.Success(body)
            } else {
                val errorMsg = response.errorBody()?.string() ?: "Ошибка входа"
                AuthResult.Error(errorMsg)
            }
        } catch (e: Exception) {
            AuthResult.Error(e.message ?: "Нет подключения к серверу")
        }
    }

    suspend fun logout() {
        try {
            api.logout()
        } catch (_: Exception) {}
        tokenStorage.clearToken()
    }

    fun isLoggedIn(): Boolean = !tokenStorage.getToken().isNullOrBlank()

    /** Получить текущий FCM-токен и зарегистрировать его на сервере. */
    suspend fun registerFcmToken() {
        try {
            val fcmToken = withContext(Dispatchers.IO) {
                FirebaseMessaging.getInstance().token.await()
            }
            api.registerDevice(DeviceTokenRequest(fcmToken = fcmToken))
        } catch (_: Exception) {
            // Не критично — onNewToken() зарегистрирует токен при следующем обновлении
        }
    }
}
