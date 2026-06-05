package com.edinykontur.observer.fcm

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import com.edinykontur.observer.MainActivity
import com.edinykontur.observer.R
import com.edinykontur.observer.data.api.ApiService
import com.edinykontur.observer.data.api.dto.DeviceTokenRequest
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import javax.inject.Inject

@AndroidEntryPoint
class EdinyKonturMessagingService : FirebaseMessagingService() {

    @Inject
    lateinit var apiService: ApiService

    /** Новый FCM-токен — регистрируем на сервере. */
    override fun onNewToken(token: String) {
        super.onNewToken(token)
        CoroutineScope(Dispatchers.IO).launch {
            try {
                apiService.registerDevice(DeviceTokenRequest(fcm_token = token))
            } catch (_: Exception) {}
        }
    }

    /** Входящее push-уведомление. */
    override fun onMessageReceived(message: RemoteMessage) {
        super.onMessageReceived(message)

        val title = message.data["title"]
            ?: message.notification?.title
            ?: "Единый Контур"
        val body = message.data["body"]
            ?: message.notification?.body
            ?: ""
        val requestId = message.data["request_id"]?.toIntOrNull()

        showNotification(title, body, requestId)
    }

    private fun showNotification(title: String, body: String, requestId: Int?) {
        val channelId = "ek_default"
        val notifManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                channelId,
                "Единый Контур",
                NotificationManager.IMPORTANCE_HIGH,
            ).apply { description = "Уведомления по заявкам" }
            notifManager.createNotificationChannel(channel)
        }

        // Intent — открыть деталь заявки или список
        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
            if (requestId != null) putExtra("request_id", requestId)
        }
        val pendingIntent = PendingIntent.getActivity(
            this, requestId ?: 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        val notification = NotificationCompat.Builder(this, channelId)
            .setSmallIcon(R.drawable.ic_splash_logo)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .build()

        notifManager.notify(requestId ?: System.currentTimeMillis().toInt(), notification)
    }
}
