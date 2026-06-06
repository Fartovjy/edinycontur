package com.edinykontur.observer.ui.detail

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.edinykontur.observer.data.api.dto.RequestDetailDto
import com.edinykontur.observer.ui.list.StatusBadge
import com.edinykontur.observer.ui.theme.EkColors

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RequestDetailScreen(
    requestId: Int,
    onBack: () -> Unit,
    viewModel: DetailViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    LaunchedEffect(requestId) { viewModel.load(requestId) }

    Scaffold(
        containerColor = EkColors.Bg,
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        uiState.request?.requestNumber ?: "Заявка",
                        fontWeight = FontWeight.Bold,
                        fontSize = 18.sp,
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Назад")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = EkColors.BrownDark,
                    titleContentColor = EkColors.Amber,
                    navigationIconContentColor = EkColors.Amber,
                ),
            )
        }
    ) { padding ->
        when {
            uiState.isLoading -> Box(
                Modifier.fillMaxSize().padding(padding),
                contentAlignment = Alignment.Center,
            ) { CircularProgressIndicator(color = EkColors.Amber) }

            uiState.error != null -> Box(
                Modifier.fillMaxSize().padding(padding),
                contentAlignment = Alignment.Center,
            ) {
                Text(uiState.error ?: "Ошибка", color = EkColors.Red, modifier = Modifier.padding(16.dp))
            }

            uiState.request != null -> {
                RequestDetailContent(
                    request = uiState.request!!,
                    modifier = Modifier.padding(padding),
                )
            }
        }
    }
}

@Composable
fun RequestDetailContent(request: RequestDetailDto, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val scroll = rememberScrollState()

    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(scroll)
            .padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        // Статус
        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            StatusBadge(request.status, request.statusDisplay)
            if (request.hasOpenProblem) {
                Surface(
                    shape = MaterialTheme.shapes.small,
                    color = EkColors.RedLight,
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
                        horizontalArrangement = Arrangement.spacedBy(4.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Icon(Icons.Default.Warning, null, tint = EkColors.Red, modifier = Modifier.size(14.dp))
                        Text("Проблема", color = EkColors.Red, fontSize = 11.sp, fontWeight = FontWeight.Medium)
                    }
                }
            }
        }

        // Клиент
        DetailSection(title = "Клиент") {
            DetailRow("Наименование", request.clientName)
            if (!request.region.isNullOrBlank()) DetailRow("Регион", request.region)
            if (!request.clientAddress.isNullOrBlank()) DetailRow("Адрес", request.clientAddress)
            if (!request.clientContact.isNullOrBlank()) DetailRow("Контакт", request.clientContact)
            if (!request.clientPhone.isNullOrBlank()) {
                DetailRowClickable(
                    label = "Телефон",
                    value = request.clientPhone,
                    onClick = {
                        val intent = Intent(Intent.ACTION_DIAL, Uri.parse("tel:${request.clientPhone.trim()}"))
                        context.startActivity(intent)
                    }
                )
            }
        }

        // Груз
        DetailSection(title = "Груз") {
            if (!request.cargoDescription.isNullOrBlank()) DetailRow("Описание", request.cargoDescription)
            DetailRow("Мест", request.cargoPlacesCount.toString())
            if (!request.cargoWeightKg.isNullOrBlank() && request.cargoWeightKg != "0.00") DetailRow("Вес", "${request.cargoWeightKg} кг")
            if (!request.cargoVolumeM3.isNullOrBlank() && request.cargoVolumeM3 != "0.000") DetailRow("Объём", "${request.cargoVolumeM3} м³")
            if (!request.dimensionsText.isNullOrBlank()) DetailRow("Габариты", request.dimensionsText)
        }

        // Даты (timeline)
        DetailSection(title = "Даты") {
            TimelineRow("Поставка запрошена", request.supplyEtaDate)
            TimelineRow("Прибытие на склад", request.warehouseArrivalDate)
            TimelineRow("Плановая отгрузка", request.plannedShipDate)
            TimelineRow("Фактическая отгрузка", request.actualShipDate)
            TimelineRow("Плановая доставка", request.plannedDeliveryDate, isPrimary = true)
            TimelineRow("Фактическая доставка", request.actualDeliveryDate)
        }

        // Транспорт
        if (!request.vehiclePlate.isNullOrBlank() || !request.driverName.isNullOrBlank()) {
            DetailSection(title = "Транспорт") {
                if (!request.warehouseName.isNullOrBlank()) DetailRow("Склад", request.warehouseName)
                if (!request.vehiclePlate.isNullOrBlank()) DetailRow("Автомобиль", request.vehiclePlate)
                if (!request.driverName.isNullOrBlank()) DetailRow("Водитель", request.driverName)
            }
        }

        // ЧЗ
        if (request.czRequired) {
            DetailSection(title = "Честный Знак") {
                if (!request.czStatusDisplay.isNullOrBlank()) DetailRow("Статус", request.czStatusDisplay)
                if (!request.czComment.isNullOrBlank()) DetailRow("Комментарий", request.czComment)
            }
        }

        // Открытые проблемы
        if (request.openProblems.isNotEmpty()) {
            DetailSection(title = "⚠ Проблемы") {
                request.openProblems.forEach { problem ->
                    Card(
                        colors = CardDefaults.cardColors(containerColor = EkColors.RedLight),
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Column(Modifier.padding(10.dp)) {
                            Text(problem.problemTypeDisplay, fontWeight = FontWeight.SemiBold, color = EkColors.Red, fontSize = 13.sp)
                            Text(problem.description, fontSize = 13.sp, color = EkColors.BrownDarkest)
                        }
                    }
                    Spacer(Modifier.height(4.dp))
                }
            }
        }

        // История статусов
        if (request.statusHistory.isNotEmpty()) {
            DetailSection(title = "История статусов") {
                request.statusHistory.take(10).forEach { h ->
                    Row(
                        modifier = Modifier.padding(vertical = 3.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Text("→", color = EkColors.Amber, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                        Column {
                            Text(h.newStatusDisplay, fontSize = 13.sp, fontWeight = FontWeight.Medium, color = EkColors.Text)
                            Text(
                                buildString {
                                    append(h.createdAt.take(10))
                                    if (!h.changedByName.isNullOrBlank()) append(" · ${h.changedByName}")
                                },
                                fontSize = 11.sp,
                                color = EkColors.Muted,
                            )
                        }
                    }
                }
            }
        }

        Spacer(Modifier.height(16.dp))
    }
}

@Composable
fun DetailSection(title: String, content: @Composable ColumnScope.() -> Unit) {
    Card(
        colors = CardDefaults.cardColors(containerColor = EkColors.Surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(title, fontWeight = FontWeight.SemiBold, fontSize = 13.sp, color = EkColors.Muted)
            HorizontalDivider(modifier = Modifier.padding(vertical = 6.dp), color = EkColors.Border)
            content()
        }
    }
}

@Composable
fun DetailRow(label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 2.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(label, fontSize = 13.sp, color = EkColors.Muted, modifier = Modifier.weight(0.45f))
        Text(value, fontSize = 13.sp, color = EkColors.Text, modifier = Modifier.weight(0.55f))
    }
}

@Composable
fun DetailRowClickable(label: String, value: String, onClick: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 2.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(label, fontSize = 13.sp, color = EkColors.Muted, modifier = Modifier.weight(0.45f))
        TextButton(
            onClick = onClick,
            contentPadding = PaddingValues(0.dp),
            modifier = Modifier.weight(0.55f),
        ) {
            Text(value, fontSize = 13.sp, color = EkColors.AmberDarker)
        }
    }
}

@Composable
fun TimelineRow(label: String, date: String?, isPrimary: Boolean = false) {
    if (date.isNullOrBlank()) return
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 2.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        val dotColor = if (isPrimary) EkColors.Amber else EkColors.GreenDark
        Box(
            modifier = Modifier
                .size(8.dp)
                .background(dotColor, shape = MaterialTheme.shapes.small),
        )
        Text(label, fontSize = 13.sp, color = EkColors.Muted, modifier = Modifier.weight(1f))
        Text(
            date.take(10),
            fontSize = 13.sp,
            fontWeight = if (isPrimary) FontWeight.SemiBold else FontWeight.Normal,
            color = if (isPrimary) EkColors.AmberDarker else EkColors.Text,
        )
    }
}
