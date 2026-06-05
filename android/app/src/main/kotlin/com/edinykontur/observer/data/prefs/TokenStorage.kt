package com.edinykontur.observer.data.prefs

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Безопасное хранение токена авторизации через EncryptedSharedPreferences.
 */
@Singleton
class TokenStorage @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private val prefs by lazy {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()

        EncryptedSharedPreferences.create(
            context,
            "ek_secure_prefs",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    fun saveToken(token: String) = prefs.edit().putString(KEY_TOKEN, token).apply()
    fun getToken(): String? = prefs.getString(KEY_TOKEN, null)
    fun clearToken() = prefs.edit().remove(KEY_TOKEN).apply()

    fun saveLastSyncAt(iso: String) = prefs.edit().putString(KEY_LAST_SYNC, iso).apply()
    fun getLastSyncAt(): String? = prefs.getString(KEY_LAST_SYNC, null)

    companion object {
        private const val KEY_TOKEN = "auth_token"
        private const val KEY_LAST_SYNC = "last_sync_at"
    }
}
