package com.edinykontur.driver.data.api

import com.edinykontur.driver.data.prefs.TokenStorage
import okhttp3.Interceptor
import okhttp3.Response
import javax.inject.Inject

/**
 * Добавляет `Authorization: Token <xxx>` ко всем запросам, кроме login.
 */
class AuthInterceptor @Inject constructor(
    private val tokenStorage: TokenStorage,
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        if (request.url.encodedPath.contains("/auth/login/")) {
            return chain.proceed(request)
        }
        val token = tokenStorage.getToken()
        if (token.isNullOrBlank()) return chain.proceed(request)
        return chain.proceed(
            request.newBuilder()
                .header("Authorization", "Token $token")
                .build()
        )
    }
}
