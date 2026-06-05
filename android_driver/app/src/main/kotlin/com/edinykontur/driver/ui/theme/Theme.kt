package com.edinykontur.driver.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val DriverColorScheme = lightColorScheme(
    primary            = DrvColors.Green,
    onPrimary          = DrvColors.Surface,
    primaryContainer   = DrvColors.GreenLight,
    onPrimaryContainer = DrvColors.GreenDarker,
    secondary          = DrvColors.GreenDark,
    onSecondary        = DrvColors.Surface,
    background         = DrvColors.Bg,
    onBackground       = DrvColors.Text,
    surface            = DrvColors.Surface,
    onSurface          = DrvColors.Text,
    surfaceVariant     = DrvColors.GreenLight,
    onSurfaceVariant   = DrvColors.Muted,
    outline            = DrvColors.Border,
    error              = DrvColors.Red,
    onError            = DrvColors.Surface,
)

@Composable
fun DriverTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = DriverColorScheme,
        typography  = DriverTypography,
        content     = content,
    )
}
