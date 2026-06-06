package com.edinykontur.observer

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import com.edinykontur.observer.data.api.ApiService
import com.edinykontur.observer.data.api.dto.DeviceTokenRequest
import com.edinykontur.observer.data.prefs.TokenStorage
import com.edinykontur.observer.navigation.NavGraph
import com.edinykontur.observer.ui.theme.EdinyKonturTheme
import com.google.firebase.messaging.FirebaseMessaging
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject lateinit var tokenStorage: TokenStorage
    @Inject lateinit var apiService: ApiService

    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        // Регистрируем FCM токен при каждом старте (если пользователь залогинен)
        if (tokenStorage.getToken() != null) {
            FirebaseMessaging.getInstance().token.addOnSuccessListener { fcmToken ->
                CoroutineScope(Dispatchers.IO).launch {
                    try { apiService.registerDevice(DeviceTokenRequest(fcmToken = fcmToken)) } catch (_: Exception) {}
                }
            }
        }

        setContent {
            EdinyKonturTheme {
                NavGraph(isLoggedIn = tokenStorage.getToken() != null)
            }
        }
    }
}
