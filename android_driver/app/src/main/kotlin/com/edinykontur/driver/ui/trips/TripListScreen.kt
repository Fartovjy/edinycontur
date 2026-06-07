package com.edinykontur.driver.ui.trips

import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.edinykontur.driver.data.api.dto.TripListItem
import com.edinykontur.driver.ui.theme.DrvColors

/** Отслеживает состояние сети через ConnectivityManager. */
@Composable
private fun rememberIsOffline(): Boolean {
    val context = LocalContext.current
    val cm = remember { context.getSystemService(ConnectivityManager::class.java) }
    val initiallyOffline = remember {
        val caps = cm.getNetworkCapabilities(cm.activeNetwork)
        caps == null || !caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }
    var isOffline by remember { mutableStateOf(initiallyOffline) }

    DisposableEffect(Unit) {
        val callback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) { isOffline = false }
            override fun onLost(network: Network) { isOffline = true }
            override fun onCapabilitiesChanged(
                network: Network,
                caps: NetworkCapabilities,
            ) { isOffline = !caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) }
        }
        val req = NetworkRequest.Builder()
            .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .build()
        cm.registerNetworkCallback(req, callback)
        onDispose { cm.unregisterNetworkCallback(callback) }
    }
    return isOffline
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TripListScreen(
    onTripClick:      (Int) -> Unit,
    onBreakdownClick: () -> Unit,
    onLogout:         () -> Unit,
    viewModel: TripListViewModel = hiltViewModel(),
) {
    val uiState   by viewModel.uiState.collectAsStateWithLifecycle()
    val isOffline = rememberIsOffline()

    // При возврате на экран — обновляем список рейсов
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) viewModel.refresh()
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text("ЕК Водитель", fontWeight = FontWeight.Bold, fontSize = 18.sp)
                },
                actions = {
                    // Кнопка поломки
                    IconButton(onClick = onBreakdownClick) {
                        Icon(
                            Icons.Default.Build,
                            contentDescription = "Поломка",
                            tint = DrvColors.Red,
                        )
                    }
                    // Меню выход
                    var menuExpanded by remember { mutableStateOf(false) }
                    IconButton(onClick = { menuExpanded = true }) {
                        Icon(Icons.Default.MoreVert, contentDescription = "Меню")
                    }
                    DropdownMenu(
                        expanded = menuExpanded,
                        onDismissRequest = { menuExpanded = false },
                    ) {
                        DropdownMenuItem(
                            text = { Text("Выйти") },
                            onClick = {
                                menuExpanded = false
                                viewModel.logout(onLogout)
                            },
                            leadingIcon = { Icon(Icons.Default.Logout, null) },
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = DrvColors.Surface,
                ),
            )
        },
        containerColor = DrvColors.Bg,
    ) { padding ->
        Column(modifier = Modifier.padding(padding).fillMaxSize()) {
            // Офлайн-баннер
            if (isOffline) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(Color(0xFFfef3c7))
                        .padding(horizontal = 16.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Icon(
                        Icons.Default.SignalWifiOff,
                        contentDescription = null,
                        tint = Color(0xFF92400e),
                        modifier = Modifier.size(16.dp),
                    )
                    Text(
                        "Нет сети — действия сохраняются в очередь",
                        fontSize = 12.sp,
                        color = Color(0xFF92400e),
                    )
                }
            }
            PullToRefreshBox(
                isRefreshing = uiState.isLoading,
                onRefresh    = { viewModel.loadTrips() },
                modifier     = Modifier.weight(1f),
            ) {
                if (uiState.error != null) {
                    Column(
                        modifier = Modifier.fillMaxSize(),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center,
                    ) {
                        Icon(Icons.Default.SignalWifiOff, null,
                            tint = DrvColors.Muted, modifier = Modifier.size(48.dp))
                        Spacer(Modifier.height(12.dp))
                        Text(uiState.error ?: "", color = DrvColors.Muted, fontSize = 14.sp)
                        Spacer(Modifier.height(16.dp))
                        Button(
                            onClick = { viewModel.loadTrips() },
                            colors = ButtonDefaults.buttonColors(containerColor = DrvColors.Green),
                        ) { Text("Повторить") }
                    }
                } else if (uiState.trips.isEmpty() && !uiState.isLoading) {
                    Column(
                        modifier = Modifier.fillMaxSize(),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center,
                    ) {
                        Icon(Icons.Default.CheckCircle, null,
                            tint = DrvColors.Muted, modifier = Modifier.size(48.dp))
                        Spacer(Modifier.height(12.dp))
                        Text("Рейсов нет", color = DrvColors.Muted, fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
                        Text("Нет активных или предстоящих заявок",
                            color = DrvColors.Muted, fontSize = 13.sp)
                    }
                } else {
                    LazyColumn(
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 8.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        items(uiState.trips, key = { it.id }) { trip ->
                            TripCard(trip = trip, onClick = { onTripClick(trip.id) })
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun TripCard(trip: TripListItem, onClick: () -> Unit) {
    val uriHandler = LocalUriHandler.current

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        shape  = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = DrvColors.Surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            // Заголовок: имя клиента + иконка проблемы
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    trip.clientName,
                    fontWeight = FontWeight.Bold,
                    fontSize = 15.sp,
                    color = DrvColors.Text,
                    modifier = Modifier.weight(1f),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                if (trip.hasOpenProblem) {
                    Icon(Icons.Default.Warning, null,
                        tint = DrvColors.Amber, modifier = Modifier.size(18.dp))
                }
            }

            Spacer(Modifier.height(4.dp))

            // Номер + груз
            Text(
                "№ ${trip.requestNumber}  ·  ${trip.cargoSummary}",
                fontSize = 12.sp,
                color = DrvColors.Muted,
            )

            Spacer(Modifier.height(8.dp))

            // Адрес + кнопка карт
            if (trip.clientAddress.isNotBlank()) {
                Row(
                    verticalAlignment = Alignment.Top,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(
                        trip.clientAddress,
                        fontSize = 13.sp,
                        color = DrvColors.Blue,
                        modifier = Modifier.weight(1f),
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Spacer(Modifier.width(6.dp))
                    IconButton(
                        onClick = {
                            val encoded = trip.clientAddress.replace(" ", "+")
                            uriHandler.openUri("https://yandex.ru/maps/?text=$encoded")
                        },
                        modifier = Modifier.size(32.dp),
                    ) {
                        Icon(
                            Icons.Default.Map,
                            contentDescription = "Открыть карту",
                            tint = DrvColors.Blue,
                            modifier = Modifier.size(20.dp),
                        )
                    }
                }
            }

            Spacer(Modifier.height(8.dp))

            // Строка статуса + дата доставки
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
                modifier = Modifier.fillMaxWidth(),
            ) {
                StatusChip(trip.status, trip.statusDisplay)
                val dateLabel = trip.plannedDeliveryDate?.let { "до $it" }
                    ?: trip.plannedShipDate?.let { "отгр. $it" }
                if (dateLabel != null) {
                    Text(dateLabel, fontSize = 11.sp, color = DrvColors.Muted)
                } else if (trip.nextStatusDisplay != null) {
                    Text("→ ${trip.nextStatusDisplay}", fontSize = 11.sp, color = DrvColors.Muted)
                }
            }
        }
    }
}

@Composable
private fun StatusChip(status: String, display: String) {
    // Перегружаем отображение для водителя (server display — для логиста, не для водителя)
    val driverLabel = when (status) {
        "transport_assigned" -> "Новый рейс"
        "shipped"            -> "Загрузился. В пути"
        "in_transit"         -> "Разгрузился. В пути"
        "delivered"          -> "На базе. Свободен"
        "problem"            -> "Проблема"
        else                 -> display
    }
    val (bg, fg) = when (status) {
        "transport_assigned" -> DrvColors.AmberLight to DrvColors.Amber
        "shipped"            -> DrvColors.BlueLight  to DrvColors.Blue
        "in_transit"         -> Color(0xFFe0f2fe)    to Color(0xFF0369a1)
        "delivered"          -> DrvColors.GreenLight to DrvColors.Green
        "problem"            -> DrvColors.RedLight   to DrvColors.Red
        else                 -> DrvColors.Bg         to DrvColors.Muted
    }
    Surface(
        color = bg,
        shape = RoundedCornerShape(6.dp),
    ) {
        Text(
            driverLabel,
            color = fg,
            fontSize = 11.sp,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
        )
    }
}
