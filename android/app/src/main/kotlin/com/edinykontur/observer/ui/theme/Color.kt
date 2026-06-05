package com.edinykontur.observer.ui.theme

import androidx.compose.ui.graphics.Color

// ─── Цвета сайта «Единый Контур» (из base.html CSS-переменных) ────────────────

object EkColors {
    // Amber / основной акцент
    val Amber        = Color(0xFFf59e0b)
    val AmberDark    = Color(0xFFd97706)
    val AmberDarker  = Color(0xFFb45309)
    val AmberLight   = Color(0xFFfef9ec)

    // Brown / тёмные тона
    val BrownDarkest = Color(0xFF1a0c02)
    val BrownDark    = Color(0xFF2c1a0e)
    val BrownMid     = Color(0xFF7a5230)
    val BrownLight   = Color(0xFFd4a66a)
    val BrownFaint   = Color(0xFFf5ede0)

    // Green
    val Green        = Color(0xFF16a34a)
    val GreenDark    = Color(0xFF15803d)
    val GreenLight   = Color(0xFFf0fdf4)
    val GreenMid     = Color(0xFF86efac)

    // Red
    val Red          = Color(0xFFdc2626)
    val RedLight     = Color(0xFFfef2f2)

    // EK semantic
    val Bg           = Color(0xFFfdf8f2)
    val Surface      = Color(0xFFFFFFFF)
    val Border       = Color(0xFFe8d5b7)
    val Text         = Color(0xFF1a0c02)  // = BrownDarkest
    val Muted        = Color(0xFF7a5230)  // = BrownMid

    // Material3 mapping helpers
    val Primary      = Amber
    val OnPrimary    = BrownDarkest
    val PrimaryContainer = AmberLight
    val OnPrimaryContainer = AmberDarker
}
