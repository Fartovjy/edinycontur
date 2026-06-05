package com.edinykontur.observer.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val EkColorScheme = lightColorScheme(
    primary            = EkColors.Primary,
    onPrimary          = EkColors.OnPrimary,
    primaryContainer   = EkColors.PrimaryContainer,
    onPrimaryContainer = EkColors.OnPrimaryContainer,
    secondary          = EkColors.BrownMid,
    onSecondary        = EkColors.Surface,
    background         = EkColors.Bg,
    onBackground       = EkColors.Text,
    surface            = EkColors.Surface,
    onSurface          = EkColors.Text,
    surfaceVariant     = EkColors.BrownFaint,
    onSurfaceVariant   = EkColors.Muted,
    outline            = EkColors.Border,
    error              = EkColors.Red,
    onError            = EkColors.Surface,
)

@Composable
fun EdinyKonturTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = EkColorScheme,
        typography  = EkTypography,
        content     = content,
    )
}
