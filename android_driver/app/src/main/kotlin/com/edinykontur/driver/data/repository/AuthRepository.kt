package com.edinykontur.driver.data.repository

import com.edinykontur.driver.data.api.DriverApiService
import com.edinykontur.driver.data.api.dto.DeviceTokenRequest
import com.edinykontur.driver.data.api.dto.LoginRequest
import com.edinykontur.driver.data.prefs.TokenStorage
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.tasks.await
import kotlinx.coroutines.withContext
import javax.inject.Inject
import javax.inject.Singleton

sealed class AuthResult {
    data class Success(val fullName: String) : AuthResult()
    data class Error(val message: String)    : AuthResult()
}

@Singleton
class AuthRepository @Inject constructor(
    private val api: DriverApiService,
    private val tokenStorage: TokenStorage,
) {
    suspend fun login(username: String, password: String): AuthResult {
        return try {
            val response = api.login(LoginRequest(username, password))
            if (response.isSuccessful) {
                val body = response.body()!!
                tokenStorage.saveToken(body.token)
                tokenStorage.saveUserId(body.user.id)
                tokenStorage.saveUserName(body.user.fullName.ifBlank { body.user.username })
                // После каждого логина явно регистрируем текущий FCM-токен.
                // onNewToken() вызывается только при смене токена Firebase,
                // а не при смене аккаунта — поэтому регистрируем вручную.
                registerFcmToken()
                AuthResult.Success(body.user.fullName.ifBlank { body.user.username })
            } else {
                val msg = when (response.code()) {
                    400  -> "Неверный логин или пароль."
                    403  -> "Доступ запрещён. Обратитесь к администратору."
                    else -> "Ошибка сервера: ${response.code()}"
                }
                AuthResult.Error(msg)
            }
        } catch (e: Exception) {
            AuthResult.Error("Нет соединения с сервером.")
        }
    }

    suspend fun logout() {
        try { api.logout() } catch (_: Exception) {}
        tokenStorage.clearToken()
    }

    /** Получить текущий FCM-токен и зарегистрировать его на сервере. */
    private suspend fun registerFcmToken() {
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
