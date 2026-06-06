package com.edinykontur.observer.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.edinykontur.observer.ui.detail.RequestDetailScreen
import com.edinykontur.observer.ui.list.RequestListScreen
import com.edinykontur.observer.ui.login.LoginScreen

sealed class Screen(val route: String) {
    object Login : Screen("login")
    object RequestList : Screen("request_list")
    object RequestDetail : Screen("request_detail/{requestId}") {
        fun createRoute(id: Int) = "request_detail/$id"
    }
}

@Composable
fun NavGraph(isLoggedIn: Boolean = false) {
    val navController = rememberNavController()

    NavHost(
        navController    = navController,
        startDestination = if (isLoggedIn) Screen.RequestList.route else Screen.Login.route,
    ) {

        composable(Screen.Login.route) {
            LoginScreen(
                onLoginSuccess = {
                    navController.navigate(Screen.RequestList.route) {
                        popUpTo(Screen.Login.route) { inclusive = true }
                    }
                }
            )
        }

        composable(Screen.RequestList.route) {
            RequestListScreen(
                onRequestClick = { id ->
                    navController.navigate(Screen.RequestDetail.createRoute(id))
                },
                onLogout = {
                    navController.navigate(Screen.Login.route) {
                        popUpTo(Screen.RequestList.route) { inclusive = true }
                    }
                }
            )
        }

        composable(
            route = Screen.RequestDetail.route,
            arguments = listOf(navArgument("requestId") { type = NavType.IntType })
        ) { backStack ->
            val requestId = backStack.arguments!!.getInt("requestId")
            RequestDetailScreen(
                requestId = requestId,
                onBack = { navController.popBackStack() },
            )
        }
    }
}
