package com.edinykontur.driver.data.prefs

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

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
            "ek_driver_secure_prefs",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    fun saveToken(token: String) = prefs.edit().putString(KEY_TOKEN, token).apply()
    fun getToken(): String?       = prefs.getString(KEY_TOKEN, null)
    fun clearToken()              = prefs.edit().remove(KEY_TOKEN).apply()

    fun saveUserId(id: Int)   = prefs.edit().putInt(KEY_USER_ID, id).apply()
    fun getUserId(): Int       = prefs.getInt(KEY_USER_ID, -1)
    fun saveUserName(name: String) = prefs.edit().putString(KEY_USER_NAME, name).apply()
    fun getUserName(): String?     = prefs.getString(KEY_USER_NAME, null)

    companion object {
        private const val KEY_TOKEN     = "driver_auth_token"
        private const val KEY_USER_ID   = "driver_user_id"
        private const val KEY_USER_NAME = "driver_user_name"
    }
}
