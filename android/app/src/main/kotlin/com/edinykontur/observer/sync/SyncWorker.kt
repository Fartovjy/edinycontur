package com.edinykontur.observer.sync

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.*
import com.edinykontur.observer.data.repository.RequestRepository
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import java.util.concurrent.TimeUnit

/**
 * WorkManager worker — периодический инкрементальный sync (каждые 15 минут).
 * Запускается только при наличии сети.
 */
@HiltWorker
class SyncWorker @AssistedInject constructor(
    @Assisted context: Context,
    @Assisted params: WorkerParameters,
    private val requestRepository: RequestRepository,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        return try {
            requestRepository.fetchRequests(incremental = true)
            Result.success()
        } catch (e: Exception) {
            Result.retry()
        }
    }

    companion object {
        private const val WORK_NAME = "ek_periodic_sync"

        /** Зарегистрировать периодический sync при старте приложения. */
        fun schedule(context: Context) {
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()

            val request = PeriodicWorkRequestBuilder<SyncWorker>(15, TimeUnit.MINUTES)
                .setConstraints(constraints)
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 1, TimeUnit.MINUTES)
                .build()

            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                WORK_NAME,
                ExistingPeriodicWorkPolicy.KEEP,
                request,
            )
        }
    }
}
