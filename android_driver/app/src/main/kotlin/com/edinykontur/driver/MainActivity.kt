package com.edinykontur.driver

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import com.edinykontur.driver.data.api.DriverApiService
import com.edinykontur.driver.data.api.dto.AppVersionInfo
import com.edinykontur.driver.data.api.dto.DeviceTokenRequest
import com.edinykontur.driver.data.prefs.TokenStorage
import com.edinykontur.driver.navigation.NavGraph
import com.edinykontur.driver.ui.theme.DriverTheme
import com.google.firebase.messaging.FirebaseMessaging
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject lateinit var tokenStorage: TokenStorage
    @Inject lateinit var api: DriverApiService

    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        // Регистрируем FCM токен при каждом старте приложения (если пользователь залогинен)
        if (tokenStorage.getToken() != null) {
            FirebaseMessaging.getInstance().token.addOnSuccessListener { fcmToken ->
                CoroutineScope(Dispatchers.IO).launch {
                    try { api.registerDevice(DeviceTokenRequest(fcmToken = fcmToken)) } catch (_: Exception) {}
                }
            }
        }

        setContent {
            DriverTheme {
                var updateInfo by remember { mutableStateOf<AppVersionInfo?>(null) }
                var isMandatory by remember { mutableStateOf(false) }

                // Проверка версии при старте
                androidx.compose.runtime.LaunchedEffect(Unit) {
                    try {
                        val response = withContext(Dispatchers.IO) { api.getAppVersion() }
                        if (response.isSuccessful) {
                            val body = response.body()?.driver ?: return@LaunchedEffect
                            val current = BuildConfig.VERSION_NAME
                            if (isNewerVersion(body.latestVersion, current)) {
                                updateInfo = body
                                isMandatory = isNewerVersion(body.minVersion, current)
                            }
                        }
                    } catch (_: Exception) {
                        // Нет сети — не блокируем работу
                    }
                }

                // Диалог обновления
                updateInfo?.let { info ->
                    AlertDialog(
                        onDismissRequest = { if (!isMandatory) updateInfo = null },
                        title = { Text("Доступно обновление") },
                        text  = {
                            Text(
                                if (isMandatory)
                                    "Версия ${info.latestVersion} обязательна для работы. Установите обновление."
                                else
                                    "Доступна новая версия ${info.latestVersion}. Рекомендуем обновить приложение."
                            )
                        },
                        confirmButton = {
                            TextButton(onClick = {
                                startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(info.downloadUrl)))
                            }) { Text("Скачать") }
                        },
                        dismissButton = if (!isMandatory) {
                            { TextButton(onClick = { updateInfo = null }) { Text("Позже") } }
                        } else null,
                    )
                }

                NavGraph(isLoggedIn = tokenStorage.getToken() != null)
            }
        }
    }
}

/** Возвращает true, если [newer] > [current] (сравниваются как "1.2.3"). */
private fun isNewerVersion(newer: String, current: String): Boolean {
    val n = newer.split(".").map { it.toIntOrNull() ?: 0 }
    val c = current.split(".").map { it.toIntOrNull() ?: 0 }
    val len = maxOf(n.size, c.size)
    for (i in 0 until len) {
        val nv = n.getOrElse(i) { 0 }
        val cv = c.getOrElse(i) { 0 }
        if (nv > cv) return true
        if (nv < cv) return false
    }
    return false
}
