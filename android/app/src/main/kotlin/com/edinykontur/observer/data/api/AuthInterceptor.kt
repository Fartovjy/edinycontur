package com.edinykontur.observer.data.api

import com.edinykontur.observer.data.prefs.TokenStorage
import okhttp3.Interceptor
import okhttp3.Response
import javax.inject.Inject

/**
 * OkHttp interceptor — добавляет заголовок `Authorization: Token <xxx>`
 * ко всем запросам, кроме auth/login/.
 */
class AuthInterceptor @Inject constructor(
    private val tokenStorage: TokenStorage,
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val originalRequest = chain.request()

        // /auth/login/ не требует токена
        if (originalRequest.url.encodedPath.contains("/auth/login/")) {
            return chain.proceed(originalRequest)
        }

        val token = tokenStorage.getToken()
        if (token.isNullOrBlank()) {
            return chain.proceed(originalRequest)
        }

        val newRequest = originalRequest.newBuilder()
            .header("Authorization", "Token $token")
            .build()
        return chain.proceed(newRequest)
    }
}
