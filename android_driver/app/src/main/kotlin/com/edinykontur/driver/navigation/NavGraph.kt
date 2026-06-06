package com.edinykontur.driver.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.edinykontur.driver.ui.breakdown.BreakdownScreen
import com.edinykontur.driver.ui.detail.TripDetailScreen
import com.edinykontur.driver.ui.login.LoginScreen
import com.edinykontur.driver.ui.trips.TripListScreen

sealed class Screen(val route: String) {
    object Login     : Screen("login")
    object TripList  : Screen("trip_list")
    object TripDetail : Screen("trip_detail/{tripId}") {
        fun createRoute(id: Int) = "trip_detail/$id"
    }
    object Breakdown : Screen("breakdown")
}

@Composable
fun NavGraph(isLoggedIn: Boolean = false) {
    val navController = rememberNavController()

    NavHost(
        navController    = navController,
        startDestination = if (isLoggedIn) Screen.TripList.route else Screen.Login.route,
    ) {

        composable(Screen.Login.route) {
            LoginScreen(
                onLoginSuccess = {
                    navController.navigate(Screen.TripList.route) {
                        popUpTo(Screen.Login.route) { inclusive = true }
                    }
                }
            )
        }

        composable(Screen.TripList.route) {
            TripListScreen(
                onTripClick = { id ->
                    navController.navigate(Screen.TripDetail.createRoute(id))
                },
                onBreakdownClick = {
                    navController.navigate(Screen.Breakdown.route)
                },
                onLogout = {
                    navController.navigate(Screen.Login.route) {
                        popUpTo(Screen.TripList.route) { inclusive = true }
                    }
                },
            )
        }

        composable(
            route = Screen.TripDetail.route,
            arguments = listOf(navArgument("tripId") { type = NavType.IntType }),
        ) { backStack ->
            val tripId = backStack.arguments!!.getInt("tripId")
            TripDetailScreen(
                tripId = tripId,
                onBack = { navController.popBackStack() },
            )
        }

        composable(Screen.Breakdown.route) {
            BreakdownScreen(
                onBack = { navController.popBackStack() },
            )
        }
    }
}
