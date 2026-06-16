package com.edinykontur.observer.ui.list

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
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
            Column {
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
                // ── Фильтр-таб ──────────────────────────────────────────────
                FilterTabRow(
                    selected      = uiState.filter,
                    activeCount   = uiState.activeCount,
                    problemCount  = uiState.problemCount,
                    archiveCount  = uiState.archiveCount,
                    onSelect      = viewModel::setFilter,
                )
            }
        }
    ) { paddingValues ->

        PullToRefreshBox(
            isRefreshing = uiState.isRefreshing,
            onRefresh    = viewModel::refresh,
            modifier     = Modifier.fillMaxSize().padding(paddingValues),
        ) {
            when {
                uiState.isLoading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = EkColors.Amber)
                }

                uiState.error != null -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(uiState.error ?: stringResource(R.string.error_loading),
                            color = EkColors.Red, modifier = Modifier.padding(16.dp))
                        Button(onClick = viewModel::refresh,
                            colors = ButtonDefaults.buttonColors(containerColor = EkColors.Amber)) {
                            Text("Повторить")
                        }
                    }
                }

                uiState.requests.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text(
                        when (uiState.filter) {
                            RequestFilter.ACTIVE   -> "Нет активных заявок"
                            RequestFilter.PROBLEMS -> "Нет заявок с ошибками"
                            RequestFilter.ARCHIVE  -> "Архив пуст"
                        },
                        color = EkColors.Muted,
                    )
                }

                else -> LazyColumn(
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

// ── Три пилюли-фильтра ──────────────────────────────────────────────────────────

@Composable
private fun FilterTabRow(
    selected:     RequestFilter,
    activeCount:  Int,
    problemCount: Int,
    archiveCount: Int,
    onSelect:     (RequestFilter) -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 8.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        FilterPill(
            label    = "Текущие",
            count    = activeCount,
            active   = selected == RequestFilter.ACTIVE,
            onClick  = { onSelect(RequestFilter.ACTIVE) },
            modifier = Modifier.weight(1f),
        )
        FilterPill(
            label    = "С ошибками",
            count    = problemCount,
            active   = selected == RequestFilter.PROBLEMS,
            onClick  = { onSelect(RequestFilter.PROBLEMS) },
            warn     = problemCount > 0,
            modifier = Modifier.weight(1f),
        )
        FilterPill(
            label    = "Архив",
            count    = archiveCount,
            active   = selected == RequestFilter.ARCHIVE,
            onClick  = { onSelect(RequestFilter.ARCHIVE) },
            modifier = Modifier.weight(1f),
        )
    }
}

@Composable
private fun FilterPill(
    label:    String,
    count:    Int,
    active:   Boolean,
    onClick:  () -> Unit,
    warn:     Boolean = false,
    modifier: Modifier = Modifier,
) {
    val shape = RoundedCornerShape(12.dp)

    val bg = when {
        active  -> EkColors.Amber
        warn    -> EkColors.Red.copy(alpha = 0.15f)
        else    -> EkColors.BrownFaint
    }
    val border = when {
        active  -> BorderStroke(1.5.dp, EkColors.Amber)
        warn    -> BorderStroke(1.dp, EkColors.Red.copy(alpha = 0.4f))
        else    -> BorderStroke(1.dp, EkColors.BrownFaint)
    }
    val fg = when {
        active  -> EkColors.BrownDarkest
        warn    -> EkColors.Red
        else    -> EkColors.Muted
    }

    Surface(
        shape  = shape,
        color  = bg,
        border = border,
        modifier = modifier.clickable(onClick = onClick),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 10.dp, horizontal = 6.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                label,
                fontSize   = 13.sp,
                fontWeight = if (active) FontWeight.Bold else FontWeight.Medium,
                color      = fg,
                maxLines   = 1,
            )
            if (count > 0) {
                Text(
                    text       = if (active) "● $count" else "$count",
                    fontSize   = 12.sp,
                    fontWeight = FontWeight.SemiBold,
                    color      = fg.copy(alpha = if (active) 1f else 0.8f),
                )
            }
        }
    }
}

// ── Карточка заявки ────────────────────────────────────────────────────────────

@Composable
fun RequestCard(
    item:     RequestListItemDto,
    onClick:  () -> Unit,
    modifier: Modifier = Modifier,
) {
    val isCompleted = item.status in setOf("delivered", "closed", "cancelled")

    Card(
        modifier  = modifier.fillMaxWidth().clickable(onClick = onClick),
        colors    = CardDefaults.cardColors(
            containerColor = if (isCompleted) EkColors.BrownFaint.copy(alpha = 0.5f) else EkColors.Surface,
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = if (isCompleted) 0.dp else 2.dp),
    ) {
        Row(modifier = Modifier.padding(14.dp), verticalAlignment = Alignment.Top) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text       = item.clientName,
                    fontWeight = FontWeight.Bold,
                    fontSize   = 17.sp,
                    color      = if (isCompleted) EkColors.Muted else EkColors.BrownDarkest,
                    maxLines   = 2,
                    overflow   = TextOverflow.Ellipsis,
                )
                Spacer(Modifier.height(4.dp))
                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment     = Alignment.CenterVertically,
                ) {
                    Text("№ ${item.requestNumber}", fontSize = 12.sp, color = EkColors.Muted)
                    if (!item.plannedDeliveryDate.isNullOrBlank()) {
                        Text("·", fontSize = 12.sp, color = EkColors.Muted)
                        Text(
                            "дост. ${item.plannedDeliveryDate.take(10)}",
                            fontSize = 12.sp, color = EkColors.Muted,
                        )
                    }
                }
                Spacer(Modifier.height(6.dp))
                StatusBadge(status = item.status, label = item.statusDisplay)
            }

            if (item.hasOpenProblem) {
                Spacer(Modifier.width(8.dp))
                Icon(Icons.Default.Warning, contentDescription = "Проблема",
                    tint = EkColors.Red, modifier = Modifier.size(22.dp))
            }
        }
    }
}

@Composable
fun StatusBadge(status: String, label: String) {
    val (bg, fg) = when (status) {
        "problem"               -> EkColors.RedLight    to EkColors.Red
        "delivered", "closed"   -> EkColors.GreenLight  to EkColors.GreenDark
        "cancelled"             -> EkColors.BrownFaint  to EkColors.Muted
        "shipped", "in_transit" -> EkColors.PrimaryContainer to EkColors.AmberDarker
        else                    -> EkColors.BrownFaint  to EkColors.Muted
    }
    Surface(shape = MaterialTheme.shapes.small, color = bg, modifier = Modifier.wrapContentSize()) {
        Text(label, color = fg, fontSize = 11.sp, fontWeight = FontWeight.Medium,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp))
    }
}
