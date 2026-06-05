package com.edinykontur.driver.ui.breakdown

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.edinykontur.driver.ui.theme.DrvColors

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BreakdownScreen(
    onBack: () -> Unit,
    viewModel: BreakdownViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    var description by remember { mutableStateOf("") }

    // Успех → диалог
    if (uiState.success) {
        AlertDialog(
            onDismissRequest = onBack,
            icon  = { Icon(Icons.Default.Warning, null, tint = DrvColors.Green) },
            title = { Text("Сообщение отправлено") },
            text  = { Text("Транспортный отдел получил уведомление о поломке.") },
            confirmButton = {
                TextButton(onClick = onBack) { Text("OK") }
            },
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Поломка автомобиля", fontWeight = FontWeight.Bold) },
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
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            // Заголовок-предупреждение
            Surface(
                color = DrvColors.RedLight,
                shape = MaterialTheme.shapes.medium,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Row(
                    modifier = Modifier.padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    Icon(Icons.Default.Warning, null,
                        tint = DrvColors.Red, modifier = Modifier.size(28.dp))
                    Column {
                        Text("Сообщить о поломке",
                            fontWeight = FontWeight.Bold, color = DrvColors.Red, fontSize = 15.sp)
                        Text("Уведомление будет отправлено транспортному отделу",
                            fontSize = 12.sp, color = DrvColors.Red)
                    }
                }
            }

            // Описание
            OutlinedTextField(
                value = description,
                onValueChange = { description = it },
                label = { Text("Описание проблемы") },
                placeholder = { Text("Опишите, что случилось с автомобилем...") },
                modifier = Modifier.fillMaxWidth().height(140.dp),
                maxLines = 6,
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = DrvColors.Red,
                    focusedLabelColor  = DrvColors.Red,
                ),
            )

            if (uiState.error != null) {
                Text(uiState.error ?: "", color = DrvColors.Red, fontSize = 13.sp)
            }

            Spacer(Modifier.weight(1f))

            Button(
                onClick = { viewModel.send(description.trim()) },
                enabled = !uiState.isSending && description.isNotBlank(),
                modifier = Modifier.fillMaxWidth().height(52.dp),
                colors = ButtonDefaults.buttonColors(containerColor = DrvColors.Red),
            ) {
                if (uiState.isSending) {
                    CircularProgressIndicator(Modifier.size(20.dp), color = DrvColors.Surface, strokeWidth = 2.dp)
                } else {
                    Icon(Icons.Default.Warning, null, Modifier.size(18.dp))
                    Spacer(Modifier.width(8.dp))
                    Text("Отправить диспетчеру", fontWeight = FontWeight.Bold, fontSize = 15.sp)
                }
            }
        }
    }
}
