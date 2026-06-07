package com.edinykontur.driver.ui.detail

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.FileProvider
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.compose.AsyncImage
import com.edinykontur.driver.data.api.dto.*
import com.edinykontur.driver.ui.theme.DrvColors
import java.io.File

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TripDetailScreen(
    tripId: Int,
    onBack: () -> Unit,
    viewModel: TripDetailViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val context = LocalContext.current

    LaunchedEffect(tripId) { viewModel.load(tripId) }

    // Snackbar-обратная связь
    val snackbarHostState = remember { SnackbarHostState() }
    LaunchedEffect(uiState.statusSuccess, uiState.odometerSuccess, uiState.photoSuccess, uiState.actionError) {
        val msg = when {
            uiState.actionError != null     -> uiState.actionError!!
            uiState.statusSuccess != null   -> "Статус обновлён"
            uiState.odometerSuccess         -> "Одометр сохранён"
            uiState.photoSuccess            -> "Фото загружено"
            else -> null
        }
        if (msg != null) {
            snackbarHostState.showSnackbar(msg)
            viewModel.clearActionFeedback()
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        uiState.trip?.requestNumber ?: "Заявка",
                        fontWeight = FontWeight.Bold,
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "Назад")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = DrvColors.Surface),
            )
        },
        containerColor = DrvColors.Bg,
    ) { padding ->
        when {
            uiState.isLoading -> Box(
                Modifier.fillMaxSize().padding(padding),
                contentAlignment = Alignment.Center,
            ) { CircularProgressIndicator(color = DrvColors.Green) }

            uiState.error != null -> Box(
                Modifier.fillMaxSize().padding(padding),
                contentAlignment = Alignment.Center,
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(uiState.error ?: "", color = DrvColors.Red)
                    Spacer(Modifier.height(12.dp))
                    Button(
                        onClick = { viewModel.load(tripId) },
                        colors = ButtonDefaults.buttonColors(containerColor = DrvColors.Green),
                    ) { Text("Повторить") }
                }
            }

            uiState.trip != null -> TripDetailContent(
                trip = uiState.trip!!,
                uiState = uiState,
                modifier = Modifier.padding(padding),
                onStatusUpdate           = { status -> viewModel.updateStatus(tripId, status) },
                onStatusWithOdometer     = { status, km -> viewModel.updateStatusWithOdometer(tripId, status, km) },
                onOdometerSave = { km -> viewModel.saveOdometer(tripId, km) },
                onPhotoUpload  = { uri, type -> viewModel.uploadPhoto(context, tripId, uri, type) },
            )
        }
    }
}

@Composable
private fun TripDetailContent(
    trip: TripDetail,
    uiState: TripDetailUiState,
    modifier: Modifier = Modifier,
    onStatusUpdate: (String) -> Unit,
    onStatusWithOdometer: (String, Int) -> Unit,
    onOdometerSave: (Int) -> Unit,
    onPhotoUpload:  (Uri, String) -> Unit,
) {
    val uriHandler = LocalUriHandler.current

    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(12.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        // ── 1. Клиент ──────────────────────────────────────────────────
        item {
            DetailCard(title = "Клиент") {
                InfoRow("Организация", trip.clientName)
                if (trip.clientAddress.isNotBlank()) {
                    Spacer(Modifier.height(6.dp))
                    Row(verticalAlignment = Alignment.Top) {
                        Column(Modifier.weight(1f)) {
                            InfoLabel("Адрес")
                            Text(trip.clientAddress, fontSize = 14.sp, color = DrvColors.Blue)
                        }
                        IconButton(
                            onClick = {
                                val q = trip.clientAddress.replace(" ", "+")
                                uriHandler.openUri("https://yandex.ru/maps/?text=$q")
                            },
                            modifier = Modifier.size(36.dp),
                        ) {
                            Icon(Icons.Default.Map, null, tint = DrvColors.Blue)
                        }
                    }
                }
                if (trip.clientPhone.isNotBlank()) {
                    Spacer(Modifier.height(6.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            InfoLabel("Телефон")
                            Text(trip.clientPhone, fontSize = 14.sp, color = DrvColors.Blue)
                        }
                        IconButton(
                            onClick = { uriHandler.openUri("tel:${trip.clientPhone}") },
                            modifier = Modifier.size(36.dp),
                        ) {
                            Icon(Icons.Default.Phone, null, tint = DrvColors.Green)
                        }
                    }
                }
            }
        }

        // ── 2. Груз ──────────────────────────────────────────────────
        item {
            DetailCard(title = "Груз") {
                Row(horizontalArrangement = Arrangement.spacedBy(20.dp)) {
                    InfoCol("Мест", "${trip.cargoPlacesCount}")
                    InfoCol("Вес", "${trip.cargoWeightKg} кг")
                    InfoCol("Объём", "${trip.cargoVolumeM3} м³")
                }
                if (trip.cargoDescription.isNotBlank()) {
                    Spacer(Modifier.height(8.dp))
                    InfoRow("Описание", trip.cargoDescription)
                }
                if (trip.cargoItems.isNotEmpty()) {
                    Spacer(Modifier.height(8.dp))
                    Text("Позиции:", fontSize = 12.sp, color = DrvColors.Muted, fontWeight = FontWeight.SemiBold)
                    trip.cargoItems.forEachIndexed { i, item ->
                        Text(
                            "${i + 1}. ${item.name}${if (item.qty.isNotBlank()) " — ${item.qty}" else ""}",
                            fontSize = 13.sp,
                            color = DrvColors.Text,
                        )
                    }
                }
            }
        }

        // ── 3. Действия ──────────────────────────────────────────────
        item {
            DetailCard(title = "Действия") {
                // Статус
                StatusSection(
                    trip = trip,
                    isUpdating = uiState.statusUpdating,
                    onStatusUpdate = onStatusUpdate,
                    onStatusWithOdometer = onStatusWithOdometer,
                )
                HorizontalDivider(modifier = Modifier.padding(vertical = 12.dp), color = DrvColors.Border)
                // Одометр (ручной ввод — всегда доступен)
                OdometerSection(
                    currentKm    = trip.odometerKm,
                    isSaving     = uiState.odometerSaving,
                    onSave       = onOdometerSave,
                )
            }
        }

        // ── 4. Фото ────────────────────────────────────────────────
        item {
            PhotoSection(
                photos       = trip.driverPhotos,
                isUploading  = uiState.photoUploading,
                onUpload     = onPhotoUpload,
            )
        }

        // ── 5. Проблемы ──────────────────────────────────────────────
        if (trip.openProblems.isNotEmpty()) {
            item {
                DetailCard(title = "Открытые проблемы") {
                    trip.openProblems.forEach { problem ->
                        Surface(
                            color = DrvColors.RedLight,
                            shape = RoundedCornerShape(8.dp),
                            modifier = Modifier.fillMaxWidth().padding(bottom = 6.dp),
                        ) {
                            Column(Modifier.padding(10.dp)) {
                                Text(problem.problemTypeDisplay,
                                    fontWeight = FontWeight.SemiBold,
                                    color = DrvColors.Red, fontSize = 13.sp)
                                Text(problem.description, fontSize = 13.sp, color = DrvColors.Text)
                                Text(problem.createdAt, fontSize = 11.sp, color = DrvColors.Muted)
                            }
                        }
                    }
                }
            }
        }
    }
}

// ── Вспомогательная функция: отображение статуса для водителя ─────────────────

private fun driverStatusLabel(status: String): String = when (status) {
    "transport_assigned" -> "Новый рейс"
    "shipped"            -> "Загрузился. В пути"
    "in_transit"         -> "Разгрузился. В пути"
    "delivered"          -> "На базе. Свободен"
    "problem"            -> "Проблема"
    else                 -> status
}

// ── Диалог обязательного ввода пробега ────────────────────────────────────────

@Composable
private fun OdometerRequiredDialog(
    onConfirm: (Int) -> Unit,
    onDismiss: () -> Unit,
) {
    var text by remember { mutableStateOf("") }
    val km = text.trim().toIntOrNull()

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Введите пробег") },
        text = {
            Column {
                Text(
                    "Для записи «Разгрузился. В пути» необходимо указать текущий пробег автомобиля.",
                    fontSize = 14.sp,
                )
                Spacer(Modifier.height(12.dp))
                OutlinedTextField(
                    value = text,
                    onValueChange = { text = it },
                    label = { Text("Пробег, км") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    modifier = Modifier.fillMaxWidth(),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = DrvColors.Green,
                        focusedLabelColor  = DrvColors.GreenDark,
                    ),
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = { if (km != null && km > 0) onConfirm(km) },
                enabled = km != null && km > 0,
            ) { Text("Подтвердить") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Отмена") }
        },
    )
}

// ── Секция статуса ─────────────────────────────────────────────────────────────

@Composable
private fun StatusSection(
    trip: TripDetail,
    isUpdating: Boolean,
    onStatusUpdate: (String) -> Unit,
    onStatusWithOdometer: (String, Int) -> Unit,
) {
    var showOdometerDialog by remember { mutableStateOf(false) }
    var pendingStatus by remember { mutableStateOf("") }

    if (showOdometerDialog) {
        OdometerRequiredDialog(
            onConfirm = { km ->
                showOdometerDialog = false
                onStatusWithOdometer(pendingStatus, km)
            },
            onDismiss = { showOdometerDialog = false },
        )
    }

    Column {
        InfoLabel("Текущий статус")
        Text(
            driverStatusLabel(trip.status),
            fontWeight = FontWeight.Bold,
            fontSize = 15.sp,
            color = DrvColors.Text,
        )
        Spacer(Modifier.height(10.dp))

        if (trip.allowedStatusTransitions.isNotEmpty()) {
            trip.allowedStatusTransitions.forEach { transition ->
                Button(
                    onClick = {
                        if (transition.requiresOdometer) {
                            pendingStatus = transition.status
                            showOdometerDialog = true
                        } else {
                            onStatusUpdate(transition.status)
                        }
                    },
                    enabled = !isUpdating,
                    modifier = Modifier.fillMaxWidth().height(52.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = DrvColors.Green),
                ) {
                    if (isUpdating) {
                        CircularProgressIndicator(Modifier.size(20.dp), color = DrvColors.Surface, strokeWidth = 2.dp)
                    } else {
                        Icon(Icons.Default.CheckCircle, null, Modifier.size(18.dp))
                        Spacer(Modifier.width(8.dp))
                        Text(transition.display, fontWeight = FontWeight.SemiBold, fontSize = 15.sp)
                    }
                }
                if (transition.requiresOdometer) {
                    Text(
                        "Требуется ввод пробега",
                        fontSize = 11.sp,
                        color = DrvColors.Muted,
                        modifier = Modifier.padding(start = 4.dp, bottom = 4.dp),
                    )
                } else {
                    Spacer(Modifier.height(4.dp))
                }
            }
        } else {
            Text(
                when (trip.status) {
                    "delivered" -> "✓ На базе. Свободен"
                    "closed"    -> "✓ Рейс закрыт"
                    else        -> "Нет доступных переходов"
                },
                color = DrvColors.Muted, fontSize = 13.sp,
            )
        }
    }
}

// ── Секция одометра ───────────────────────────────────────────────────────────

@Composable
private fun OdometerSection(
    currentKm: Int?,
    isSaving: Boolean,
    onSave: (Int) -> Unit,
) {
    var kmText by remember { mutableStateOf(currentKm?.toString() ?: "") }

    Column {
        InfoLabel("Одометр, км")
        if (currentKm != null) {
            Text("Последнее: $currentKm км", fontSize = 12.sp, color = DrvColors.Muted)
        }
        Spacer(Modifier.height(6.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(
                value = kmText,
                onValueChange = { kmText = it },
                label = { Text("Показание, км") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                modifier = Modifier.weight(1f),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = DrvColors.Green,
                    focusedLabelColor  = DrvColors.GreenDark,
                ),
            )
            Spacer(Modifier.width(8.dp))
            Button(
                onClick = {
                    val km = kmText.trim().toIntOrNull()
                    if (km != null && km > 0) onSave(km)
                },
                enabled = !isSaving && kmText.trim().toIntOrNull() != null,
                colors  = ButtonDefaults.buttonColors(containerColor = DrvColors.Green),
            ) {
                if (isSaving) CircularProgressIndicator(Modifier.size(18.dp), color = DrvColors.Surface, strokeWidth = 2.dp)
                else Text("Сохранить")
            }
        }
    }
}

// ── Секция фото ───────────────────────────────────────────────────────────────

@Composable
private fun PhotoSection(
    photos: List<PhotoDto>,
    isUploading: Boolean,
    onUpload: (Uri, String) -> Unit,
) {
    val context = LocalContext.current
    var showTypeDialog by remember { mutableStateOf(false) }
    var pendingUri      by remember { mutableStateOf<Uri?>(null) }

    // Создаём временный файл для камеры
    val cameraImageFile = remember {
        File(context.cacheDir, "camera_photo_${System.currentTimeMillis()}.jpg")
    }
    val cameraUri = remember(cameraImageFile) {
        FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", cameraImageFile)
    }

    val cameraLauncher = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { success ->
        if (success) { pendingUri = cameraUri; showTypeDialog = true }
    }
    val galleryLauncher = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null) { pendingUri = uri; showTypeDialog = true }
    }

    // Диалог выбора типа фото
    if (showTypeDialog && pendingUri != null) {
        AlertDialog(
            onDismissRequest = { showTypeDialog = false; pendingUri = null },
            title = { Text("Тип фото") },
            text = {
                Column {
                    listOf("loading" to "При погрузке", "delivery" to "При доставке", "problem" to "Проблема")
                        .forEach { (type, label) ->
                            TextButton(
                                onClick = {
                                    onUpload(pendingUri!!, type)
                                    showTypeDialog = false
                                    pendingUri = null
                                },
                                modifier = Modifier.fillMaxWidth(),
                            ) { Text(label, fontSize = 15.sp) }
                        }
                }
            },
            confirmButton = {},
            dismissButton = {
                TextButton(onClick = { showTypeDialog = false; pendingUri = null }) { Text("Отмена") }
            },
        )
    }

    DetailCard(title = "Фото груза (${photos.size})") {
        // Сетка фото
        if (photos.isNotEmpty()) {
            val columns = 3
            val rows = (photos.size + columns - 1) / columns
            for (row in 0 until rows) {
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    for (col in 0 until columns) {
                        val idx = row * columns + col
                        if (idx < photos.size) {
                            Box(
                                modifier = Modifier
                                    .weight(1f)
                                    .aspectRatio(1f)
                                    .background(DrvColors.GreenLight, RoundedCornerShape(8.dp)),
                            ) {
                                AsyncImage(
                                    model = photos[idx].photoUrl,
                                    contentDescription = photos[idx].photoTypeDisplay,
                                    contentScale = ContentScale.Crop,
                                    modifier = Modifier.fillMaxSize(),
                                )
                            }
                        } else {
                            Spacer(Modifier.weight(1f))
                        }
                    }
                }
                if (row < rows - 1) Spacer(Modifier.height(6.dp))
            }
            Spacer(Modifier.height(10.dp))
        }

        // Кнопки фото
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(
                onClick = { cameraLauncher.launch(cameraUri) },
                enabled = !isUploading,
                modifier = Modifier.weight(1f),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = DrvColors.Green),
            ) {
                if (isUploading) CircularProgressIndicator(Modifier.size(16.dp), color = DrvColors.Green, strokeWidth = 2.dp)
                else {
                    Icon(Icons.Default.CameraAlt, null, Modifier.size(16.dp))
                    Spacer(Modifier.width(4.dp))
                    Text("Камера", fontSize = 13.sp)
                }
            }
            OutlinedButton(
                onClick = { galleryLauncher.launch("image/*") },
                enabled = !isUploading,
                modifier = Modifier.weight(1f),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = DrvColors.Muted),
            ) {
                Icon(Icons.Default.Image, null, Modifier.size(16.dp))
                Spacer(Modifier.width(4.dp))
                Text("Галерея", fontSize = 13.sp)
            }
        }
    }
}

// ── Вспомогательные компоненты ─────────────────────────────────────────────────

@Composable
private fun DetailCard(
    title: String,
    content: @Composable ColumnScope.() -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape  = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = DrvColors.Surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Column(Modifier.padding(14.dp)) {
            Text(title, fontWeight = FontWeight.Bold, fontSize = 14.sp,
                color = DrvColors.Muted, modifier = Modifier.padding(bottom = 10.dp))
            content()
        }
    }
}

@Composable
private fun InfoLabel(text: String) {
    Text(text, fontSize = 11.sp, color = DrvColors.Muted,
        fontWeight = FontWeight.Medium, modifier = Modifier.padding(bottom = 2.dp))
}

@Composable
private fun InfoRow(label: String, value: String) {
    InfoLabel(label)
    Text(value, fontSize = 14.sp, fontWeight = FontWeight.SemiBold, color = DrvColors.Text)
}

@Composable
private fun InfoCol(label: String, value: String) {
    Column {
        InfoLabel(label)
        Text(value, fontSize = 15.sp, fontWeight = FontWeight.Bold, color = DrvColors.Text)
    }
}
