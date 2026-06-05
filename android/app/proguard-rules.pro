-keepattributes *Annotation*
-keepclassmembers class ** {
    @com.squareup.moshi.FromJson *;
    @com.squareup.moshi.ToJson *;
}
-keep class com.edinykontur.observer.data.api.dto.** { *; }
