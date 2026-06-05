package com.edinykontur.driver.di

import android.content.Context
import androidx.room.Room
import com.edinykontur.driver.data.db.DriverDatabase
import com.edinykontur.driver.data.db.PendingActionDao
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object DatabaseModule {

    @Provides
    @Singleton
    fun provideDatabase(@ApplicationContext context: Context): DriverDatabase =
        Room.databaseBuilder(context, DriverDatabase::class.java, "driver_db")
            .fallbackToDestructiveMigration()
            .build()

    @Provides
    fun providePendingActionDao(db: DriverDatabase): PendingActionDao = db.pendingActionDao()
}
