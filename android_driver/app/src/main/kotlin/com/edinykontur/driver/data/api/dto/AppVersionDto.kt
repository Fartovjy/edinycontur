package com.edinykontur.driver.data.api.dto

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class AppVersionInfo(
    @Json(name = "latest_version") val latestVersion: String,
    @Json(name = "min_version")    val minVersion: String,
    @Json(name = "download_url")   val downloadUrl: String,
)

@JsonClass(generateAdapter = true)
data class AppVersionResponse(
    @Json(name = "observer") val observer: AppVersionInfo,
    @Json(name = "driver")   val driver: AppVersionInfo,
)
