package com.edinykontur.driver.fcm

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import com.edinykontur.driver.MainActivity
import com.edinykontur.driver.R
import com.edinykontur.driver.data.api.DriverApiService
import com.edinykontur.driver.data.api.dto.DeviceTokenRequest
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import javax.inject.Inject

@AndroidEntryPoint
class DriverMessagingService : FirebaseMessagingService() {

    @Inject
    lateinit var api: DriverApiService

    /** Новый FCM-токен — немедленно регистрируем на сервере. */
    override fun onNewToken(token: String) {
        super.onNewToken(token)
        CoroutineScope(Dispatchers.IO).launch {
            try {
                api.registerDevice(DeviceTokenRequest(fcmToken = token))
            } catch (_: Exception) {}
        }
    }

    /** Входящее push-уведомление от бэкенда. */
    override fun onMessageReceived(message: RemoteMessage) {
        super.onMessageReceived(message)
        val title = message.data["title"]
            ?: message.notification?.title
            ?: "ЕК Водитель"
        val body = message.data["body"]
            ?: message.notification?.body
            ?: ""
        val requestId = message.data["request_id"]?.toIntOrNull()
        showNotification(title, body, requestId)
    }

    private fun showNotification(title: String, body: String, requestId: Int?) {
        val channelId = "ek_driver"
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            nm.createNotificationChannel(
                NotificationChannel(channelId, "ЕК Водитель", NotificationManager.IMPORTANCE_HIGH)
                    .apply { description = "Уведомления по заявкам и рейсам" }
            )
        }
        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
            if (requestId != null) putExtra("trip_id", requestId)
        }
        val pi = PendingIntent.getActivity(
            this, requestId ?: 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notif = NotificationCompat.Builder(this, channelId)
            .setSmallIcon(R.drawable.ic_splash_logo)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setAutoCancel(true)
            .setContentIntent(pi)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .build()
        nm.notify(requestId ?: System.currentTimeMillis().toInt(), notif)
    }
}
