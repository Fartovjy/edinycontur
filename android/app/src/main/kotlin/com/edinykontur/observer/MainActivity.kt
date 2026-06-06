package com.edinykontur.observer

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import com.edinykontur.observer.data.prefs.TokenStorage
import com.edinykontur.observer.navigation.NavGraph
import com.edinykontur.observer.ui.theme.EdinyKonturTheme
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject lateinit var tokenStorage: TokenStorage

    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            EdinyKonturTheme {
                NavGraph(isLoggedIn = tokenStorage.getToken() != null)
            }
        }
    }
}
