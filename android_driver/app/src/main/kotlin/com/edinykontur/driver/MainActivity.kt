package com.edinykontur.driver

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import com.edinykontur.driver.data.api.DriverApiService
import com.edinykontur.driver.data.api.dto.DeviceTokenRequest
import com.edinykontur.driver.data.prefs.TokenStorage
import com.edinykontur.driver.navigation.NavGraph
import com.edinykontur.driver.ui.theme.DriverTheme
import com.google.firebase.messaging.FirebaseMessaging
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
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
                NavGraph(isLoggedIn = tokenStorage.getToken() != null)
            }
        }
    }
}
