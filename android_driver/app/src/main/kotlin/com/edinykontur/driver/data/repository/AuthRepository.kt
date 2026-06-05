package com.edinykontur.driver.data.repository

import com.edinykontur.driver.data.api.DriverApiService
import com.edinykontur.driver.data.api.dto.LoginRequest
import com.edinykontur.driver.data.prefs.TokenStorage
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
}
