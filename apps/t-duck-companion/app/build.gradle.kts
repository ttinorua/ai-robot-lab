plugins { id("com.android.application"); id("org.jetbrains.kotlin.android"); id("org.jetbrains.kotlin.plugin.compose") }
android {
 namespace = "com.tduck.companion"
 compileSdk = 35
 defaultConfig { applicationId = "com.tduck.companion"; minSdk = 26; targetSdk = 35; versionCode = providers.gradleProperty("companionVersionCode").orElse("3").get().toInt(); versionName = "0.2.1-dev"; testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner" }
 // Owner-managed release identity only. Never fall back to a runner-generated key.
 val signingPath = System.getenv("T_DUCK_SIGNING_STORE")
 signingConfigs {
  if (!signingPath.isNullOrBlank()) create("owner") {
   storeFile = file(signingPath)
   storePassword = System.getenv("T_DUCK_SIGNING_STORE_PASSWORD") ?: error("Missing store password")
   keyAlias = System.getenv("T_DUCK_SIGNING_ALIAS") ?: error("Missing key alias")
   keyPassword = System.getenv("T_DUCK_SIGNING_KEY_PASSWORD") ?: error("Missing key password")
  }
 }
 buildTypes { getByName("release") { if (!signingPath.isNullOrBlank()) signingConfig = signingConfigs.getByName("owner") } }
 buildFeatures { compose = true }
 compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
 kotlinOptions { jvmTarget = "17" }
}
dependencies {
 implementation(platform("androidx.compose:compose-bom:2024.09.03"))
 implementation("androidx.activity:activity-compose:1.9.3")
 implementation("androidx.compose.material3:material3")
 implementation("androidx.compose.ui:ui-tooling-preview")
 implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
 implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
 implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
 androidTestImplementation(platform("androidx.compose:compose-bom:2024.09.03"))
 androidTestImplementation("androidx.compose.ui:ui-test-junit4")
 androidTestImplementation("androidx.test.ext:junit:1.2.1")
 androidTestImplementation("androidx.test:runner:1.6.2")
 androidTestImplementation("androidx.test.espresso:espresso-core:3.6.1")
 debugImplementation("androidx.compose.ui:ui-test-manifest")
 testImplementation("junit:junit:4.13.2")
 testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.9.0")
 testImplementation("org.json:json:20240303")
}
