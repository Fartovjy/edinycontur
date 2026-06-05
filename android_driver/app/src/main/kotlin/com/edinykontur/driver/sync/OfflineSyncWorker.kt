package com.edinykontur.driver.sync

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.hilt.work.HiltWorker
import androidx.work.*
import com.edinykontur.driver.data.api.DriverApiService
import com.edinykontur.driver.data.api.dto.BreakdownRequest
import com.edinykontur.driver.data.api.dto.OdometerRequest
import com.edinykontur.driver.data.api.dto.StatusChangeRequest
import com.edinykontur.driver.data.db.PendingActionDao
import com.squareup.moshi.Moshi
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File

/**
 * WorkManager worker: синхронизирует офлайн-очередь с сервером.
 * Запускается при появлении сети.
 */
@HiltWorker
class OfflineSyncWorker @AssistedInject constructor(
    @Assisted appContext: Context,
    @Assisted workerParams: WorkerParameters,
    private val pendingDao: PendingActionDao,
    private val api: DriverApiService,
    private val moshi: Moshi,
) : CoroutineWorker(appContext, workerParams) {

    override suspend fun doWork(): Result {
        val actions = pendingDao.getAll()
        if (actions.isEmpty()) return Result.success()

        var syncedCount = 0
        for (action in actions) {
            try {
                val success = when (action.type) {
                    TYPE_STATUS -> {
                        val req = moshi.adapter(StatusChangeRequest::class.java).fromJson(action.payload)!!
                        api.updateStatus(action.requestId, req).isSuccessful
                    }
                    TYPE_ODOMETER -> {
                        val req = moshi.adapter(OdometerRequest::class.java).fromJson(action.payload)!!
                        api.saveOdometer(action.requestId, req).isSuccessful
                    }
                    TYPE_PHOTO -> {
                        val file = action.photoPath?.let { File(it) }
                        if (file == null || !file.exists()) {
                            true // нет файла — удаляем из очереди
                        } else {
                            val body    = file.asRequestBody("image/jpeg".toMediaTypeOrNull())
                            val part    = MultipartBody.Part.createFormData("file", file.name, body)
                            val typePart = (action.payload).toRequestBody("text/plain".toMediaTypeOrNull())
                            val ok = api.uploadPhoto(action.requestId, part, typePart).isSuccessful
                            if (ok) file.delete()
                            ok
                        }
                    }
                    TYPE_BREAKDOWN -> {
                        val req = moshi.adapter(BreakdownRequest::class.java).fromJson(action.payload)!!
                        api.reportBreakdown(req).isSuccessful
                    }
                    else -> true
                }
                if (success) {
                    pendingDao.delete(action)
                    syncedCount++
                } else {
                    pendingDao.incrementRetry(action.id)
                }
            } catch (_: Exception) {
                pendingDao.incrementRetry(action.id)
            }
        }

        if (syncedCount > 0) {
            showSyncNotification(syncedCount)
        }

        return Result.success()
    }

    private fun showSyncNotification(count: Int) {
        val nm = applicationContext.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            nm.createNotificationChannel(
                NotificationChannel(CHANNEL_ID, "Синхронизация", NotificationManager.IMPORTANCE_LOW)
            )
        }
        val notif = NotificationCompat.Builder(applicationContext, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle("ЕК Водитель")
            .setContentText("Синхронизировано действий: $count")
            .setAutoCancel(true)
            .build()
        nm.notify(NOTIF_ID, notif)
    }

    companion object {
        const val TYPE_STATUS    = "status"
        const val TYPE_ODOMETER  = "odometer"
        const val TYPE_PHOTO     = "photo"
        const val TYPE_BREAKDOWN = "breakdown"
        private const val CHANNEL_ID = "driver_sync"
        private const val NOTIF_ID   = 1001

        fun enqueue(context: Context) {
            val request = OneTimeWorkRequestBuilder<OfflineSyncWorker>()
                .setConstraints(
                    Constraints.Builder()
                        .setRequiredNetworkType(NetworkType.CONNECTED)
                        .build()
                )
                .build()
            WorkManager.getInstance(context).enqueueUniqueWork(
                "offline_sync",
                ExistingWorkPolicy.REPLACE,
                request,
            )
        }
    }
}
