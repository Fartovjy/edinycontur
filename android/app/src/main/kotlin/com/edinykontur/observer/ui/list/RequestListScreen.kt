package com.edinykontur.observer.ui.list

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Logout
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.edinykontur.observer.R
import com.edinykontur.observer.data.api.dto.RequestListItemDto
import com.edinykontur.observer.ui.theme.EkColors

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RequestListScreen(
    onRequestClick: (Int) -> Unit,
    onLogout: () -> Unit,
    viewModel: ListViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    Scaffold(
        containerColor = EkColors.Bg,
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("Единый Контур", fontWeight = FontWeight.Bold, fontSize = 18.sp)
                        Text("Заявки", fontSize = 12.sp, color = EkColors.Muted)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = EkColors.BrownDark,
                    titleContentColor = EkColors.Amber,
                    actionIconContentColor = EkColors.Amber,
                ),
                actions = {
                    IconButton(onClick = { viewModel.logout(onLogout) }) {
                        Icon(Icons.Default.Logout, contentDescription = stringResource(R.string.logout))
                    }
                }
            )
        }
    ) { paddingValues ->

        PullToRefreshBox(
            isRefreshing = uiState.isRefreshing,
            onRefresh = viewModel::refresh,
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues),
        ) {
            when {
                uiState.isLoading -> {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(color = EkColors.Amber)
                    }
                }

                uiState.error != null -> {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(
                                uiState.error ?: stringResource(R.string.error_loading),
                                color = EkColors.Red,
                                modifier = Modifier.padding(16.dp),
                            )
                            Button(
                                onClick = viewModel::refresh,
                                colors = ButtonDefaults.buttonColors(containerColor = EkColors.Amber),
                            ) { Text("Повторить") }
                        }
                    }
                }

                uiState.requests.isEmpty() -> {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text(stringResource(R.string.no_requests), color = EkColors.Muted)
                    }
                }

                else -> {
                    LazyColumn(
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 8.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        items(uiState.requests, key = { it.id }) { request ->
                            RequestCard(request, onClick = { onRequestClick(request.id) })
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun RequestCard(
    item: RequestListItemDto,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        colors = CardDefaults.cardColors(containerColor = EkColors.Surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
    ) {
        Row(
            modifier = Modifier.padding(14.dp),
            verticalAlignment = Alignment.Top,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                // Клиент (крупно)
                Text(
                    text = item.clientName,
                    fontWeight = FontWeight.Bold,
                    fontSize = 17.sp,
                    color = EkColors.BrownDarkest,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Spacer(Modifier.height(4.dp))
                // Номер, дата, статус
                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        text = "№ ${item.requestNumber}",
                        fontSize = 12.sp,
                        color = EkColors.Muted,
                    )
                    if (!item.plannedDeliveryDate.isNullOrBlank()) {
                        Text("·", fontSize = 12.sp, color = EkColors.Muted)
                        Text(
                            text = "дост. ${item.plannedDeliveryDate.take(10)}",
                            fontSize = 12.sp,
                            color = EkColors.Muted,
                        )
                    }
                }
                Spacer(Modifier.height(6.dp))
                // Бэйдж статуса
                StatusBadge(status = item.status, label = item.statusDisplay)
            }

            // Иконка проблемы
            if (item.hasOpenProblem) {
                Spacer(Modifier.width(8.dp))
                Icon(
                    Icons.Default.Warning,
                    contentDescription = "Проблема",
                    tint = EkColors.Red,
                    modifier = Modifier.size(22.dp),
                )
            }
        }
    }
}

@Composable
fun StatusBadge(status: String, label: String) {
    val (bg, fg) = when (status) {
        "problem"             -> EkColors.RedLight  to EkColors.Red
        "delivered", "closed" -> EkColors.GreenLight to EkColors.GreenDark
        "shipped", "in_transit" -> EkColors.PrimaryContainer to EkColors.AmberDarker
        else                  -> EkColors.BrownFaint to EkColors.Muted
    }
    Surface(
        shape = MaterialTheme.shapes.small,
        color = bg,
        modifier = Modifier.wrapContentSize(),
    ) {
        Text(
            text = label,
            color = fg,
            fontSize = 11.sp,
            fontWeight = FontWeight.Medium,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
        )
    }
}
