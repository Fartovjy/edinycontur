package com.edinykontur.driver.di

import com.edinykontur.driver.BuildConfig
import com.edinykontur.driver.data.api.AuthInterceptor
import com.edinykontur.driver.data.api.DriverApiService
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import okhttp3.CertificatePinner
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import java.security.SecureRandom
import java.security.cert.X509Certificate
import java.util.concurrent.TimeUnit
import javax.inject.Singleton
import javax.net.ssl.SSLContext
import javax.net.ssl.TrustManager
import javax.net.ssl.X509TrustManager

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {

    // SPKI SHA-256 отпечаток самоподписанного сертификата сервера.
    // Обновить при перевыпуске сертификата (раз в 10 лет).
    private const val SERVER_HOST = "5.42.122.25"
    private const val CERT_PIN   = "sha256/3JP742a+v+VyOYyMFODFKPkbsoHMJyPDUCVpgiL+fTo="

    @Provides
    @Singleton
    fun provideMoshi(): Moshi = Moshi.Builder()
        .addLast(KotlinJsonAdapterFactory())
        .build()

    @Provides
    @Singleton
    fun provideOkHttpClient(authInterceptor: AuthInterceptor): OkHttpClient {
        val logging = HttpLoggingInterceptor().apply {
            level = if (BuildConfig.DEBUG)
                HttpLoggingInterceptor.Level.BODY
            else
                HttpLoggingInterceptor.Level.NONE
        }

        // Сервер использует самоподписанный сертификат (IP без домена).
        // TrustManager принимает самоподписанные сертификаты,
        // а CertificatePinner гарантирует, что это именно НАШ сертификат.
        // MITM невозможен: у атакующего нет нашего приватного ключа.
        val trustSelfSigned = arrayOf<TrustManager>(object : X509TrustManager {
            override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) {}
            override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {}
            override fun getAcceptedIssuers(): Array<X509Certificate> = arrayOf()
        })
        val sslContext = SSLContext.getInstance("TLS").apply {
            init(null, trustSelfSigned, SecureRandom())
        }

        val pinner = CertificatePinner.Builder()
            .add(SERVER_HOST, CERT_PIN)
            .build()

        return OkHttpClient.Builder()
            .sslSocketFactory(sslContext.socketFactory, trustSelfSigned[0] as X509TrustManager)
            .certificatePinner(pinner)
            .addInterceptor(authInterceptor)
            .addInterceptor(logging)
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)
            .writeTimeout(60, TimeUnit.SECONDS)
            .build()
    }

    @Provides
    @Singleton
    fun provideRetrofit(okHttpClient: OkHttpClient, moshi: Moshi): Retrofit =
        Retrofit.Builder()
            .baseUrl(BuildConfig.BASE_URL)
            .client(okHttpClient)
            .addConverterFactory(MoshiConverterFactory.create(moshi))
            .build()

    @Provides
    @Singleton
    fun provideDriverApiService(retrofit: Retrofit): DriverApiService =
        retrofit.create(DriverApiService::class.java)
}
