package com.edinykontur.driver

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import com.edinykontur.driver.data.prefs.TokenStorage
import com.edinykontur.driver.navigation.NavGraph
import com.edinykontur.driver.ui.theme.DriverTheme
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
            DriverTheme {
                NavGraph(isLoggedIn = tokenStorage.getToken() != null)
            }
        }
    }
}
