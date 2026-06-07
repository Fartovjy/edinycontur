package com.edinykontur.observer.ui.list

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.History
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
                    // Кнопка архива — подсвечена когда архив включён
                    IconButton(onClick = viewModel::toggleShowCompleted) {
                        Icon(
                            Icons.Default.History,
                            contentDescription = if (uiState.showCompleted) "Скрыть архив" else "Показать архив",
                            tint = if (uiState.showCompleted) EkColors.Amber
                                   else EkColors.Amber.copy(alpha = 0.45f),
                        )
                    }
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

                else -> {
                    LazyColumn(
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 8.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        // Баннер когда архив включён
                        if (uiState.showCompleted && uiState.completedCount > 0) {
                            item(key = "archive_banner") {
                                ArchiveBanner(
                                    activeCount    = uiState.activeCount,
                                    completedCount = uiState.completedCount,
                                    onHide         = viewModel::toggleShowCompleted,
                                )
                            }
                        }

                        if (uiState.requests.isEmpty()) {
                            item(key = "empty") {
                                Box(
                                    Modifier
                                        .fillParentMaxWidth()
                                        .padding(vertical = 64.dp),
                                    contentAlignment = Alignment.Center,
                                ) {
                                    Text(
                                        if (uiState.showCompleted) "Нет заявок"
                                        else "Нет активных заявок",
                                        color = EkColors.Muted,
                                    )
                                }
                            }
                        } else {
                            items(uiState.requests, key = { it.id }) { request ->
                                RequestCard(request, onClick = { onRequestClick(request.id) })
                            }
                        }

                        // Подсказка "показать архив" в конце активного списка
                        if (!uiState.showCompleted && uiState.completedCount > 0) {
                            item(key = "show_archive_hint") {
                                ShowArchiveHint(
                                    count   = uiState.completedCount,
                                    onClick = viewModel::toggleShowCompleted,
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

// ── Баннер "Включён архив" ─────────────────────────────────────────────────────

@Composable
private fun ArchiveBanner(activeCount: Int, completedCount: Int, onHide: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(EkColors.BrownFaint, RoundedCornerShape(8.dp))
            .padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Column {
            Text(
                "Включён архив",
                fontWeight = FontWeight.SemiBold,
                fontSize = 13.sp,
                color = EkColors.BrownDarkest,
            )
            Text(
                "Активных: $activeCount · Завершённых: $completedCount",
                fontSize = 11.sp,
                color = EkColors.Muted,
            )
        }
        TextButton(onClick = onHide) {
            Text("Скрыть", fontSize = 12.sp, color = EkColors.Amber)
        }
    }
}

// ── Подсказка в конце списка ──────────────────────────────────────────────────

@Composable
private fun ShowArchiveHint(count: Int, onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        contentAlignment = Alignment.Center,
    ) {
        TextButton(onClick = onClick) {
            Icon(
                Icons.Default.History,
                contentDescription = null,
                modifier = Modifier.size(16.dp),
                tint = EkColors.Muted,
            )
            Spacer(Modifier.width(6.dp))
            Text(
                "Показать завершённые ($count)",
                fontSize = 13.sp,
                color = EkColors.Muted,
            )
        }
    }
}

// ── Карточка заявки ────────────────────────────────────────────────────────────

@Composable
fun RequestCard(
    item: RequestListItemDto,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val isCompleted = item.status in setOf("delivered", "closed", "cancelled")

    Card(
        modifier = modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        colors = CardDefaults.cardColors(
            containerColor = if (isCompleted) EkColors.BrownFaint.copy(alpha = 0.5f)
                             else EkColors.Surface,
        ),
        elevation = CardDefaults.cardElevation(
            defaultElevation = if (isCompleted) 0.dp else 2.dp,
        ),
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
                    color = if (isCompleted) EkColors.Muted else EkColors.BrownDarkest,
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
        "cancelled"           -> EkColors.BrownFaint to EkColors.Muted
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
