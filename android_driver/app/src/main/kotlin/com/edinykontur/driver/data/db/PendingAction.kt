package com.edinykontur.driver.data.db

import androidx.room.*

/**
 * Офлайн-очередь действий водителя.
 * Пока нет сети — действия (смена статуса, одометр, фото, поломка) складываются сюда.
 * При появлении сети OfflineSyncWorker отправляет их на сервер по порядку.
 */
@Entity(tableName = "pending_actions")
data class PendingAction(
    @PrimaryKey(autoGenerate = true) val id: Int = 0,
    val type:       String,    // "status" | "odometer" | "photo" | "breakdown"
    val requestId:  Int,       // id заявки (0 если не привязано)
    val payload:    String,    // JSON с параметрами
    val photoPath:  String?,   // локальный путь к фото (только для type="photo")
    val createdAt:  Long = System.currentTimeMillis(),
    val retries:    Int = 0,
)

@Dao
interface PendingActionDao {
    @Query("SELECT * FROM pending_actions ORDER BY createdAt ASC")
    suspend fun getAll(): List<PendingAction>

    @Insert
    suspend fun insert(action: PendingAction): Long

    @Delete
    suspend fun delete(action: PendingAction)

    @Query("SELECT COUNT(*) FROM pending_actions")
    suspend fun count(): Int

    @Query("UPDATE pending_actions SET retries = retries + 1 WHERE id = :id")
    suspend fun incrementRetry(id: Int)
}

@Database(entities = [PendingAction::class], version = 1, exportSchema = false)
abstract class DriverDatabase : RoomDatabase() {
    abstract fun pendingActionDao(): PendingActionDao
}
