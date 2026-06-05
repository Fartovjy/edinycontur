package com.edinykontur.driver.ui.theme

import androidx.compose.ui.graphics.Color

/**
 * Цветовая палитра «ЕК Водитель».
 * Используем зелёный акцент вместо янтарного (чтобы не путать с Наблюдателем).
 */
object DrvColors {
    // Акцентный: зелёный
    val Green        = Color(0xFF16a34a)
    val GreenDark    = Color(0xFF15803d)
    val GreenDarker  = Color(0xFF166534)
    val GreenLight   = Color(0xFFf0fdf4)

    // Фоны и нейтральные
    val Bg           = Color(0xFFf7faf8)
    val Surface      = Color(0xFFFFFFFF)
    val Border       = Color(0xFFd1e7da)

    // Текст
    val Text         = Color(0xFF0d1f14)
    val Muted        = Color(0xFF4d7a5c)

    // Статусные
    val Red          = Color(0xFFdc2626)
    val RedLight     = Color(0xFFfef2f2)
    val Amber        = Color(0xFFf59e0b)
    val AmberLight   = Color(0xFFfefce8)
    val Blue         = Color(0xFF0284c7)
    val BlueLight    = Color(0xFFf0f9ff)
}
