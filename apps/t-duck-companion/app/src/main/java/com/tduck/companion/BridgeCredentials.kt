package com.tduck.companion

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Never use an auto-generated toString that would expose an in-memory token. */
class SavedBridge(val endpoint: String, val token: String) {
    override fun toString() = "SavedBridge(<redacted>)"
}
class CredentialRead(val connection: SavedBridge? = null, val unreadable: Boolean = false)
interface ConnectionCredentialStore {
    fun load(): CredentialRead
    fun save(url: String, token: String)
    fun clear(): Boolean
}

/** Device-bound AES-256-GCM. Existing PR7 records (without AAD) migrate on next successful save. */
internal class BridgeCredentials(context: Context) : ConnectionCredentialStore {
    private val prefs = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
    private fun store() = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
    private fun encryptionKey(): SecretKey {
        (store().getKey(ALIAS, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true).setKeySize(256).build())
        }.generateKey()
    }
    @Synchronized override fun save(url: String, token: String) {
        val endpoint = BridgeEndpoint.normalize(url)
        require(token.isNotBlank() && token.length <= 4096 && token.none { it == '\r' || it == '\n' }) { "Invalid access token" }
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, encryptionKey())
        cipher.updateAAD(endpoint.toByteArray(Charsets.UTF_8))
        val encrypted = cipher.doFinal(token.toByteArray(Charsets.UTF_8))
        check(prefs.edit().clear().putInt("format", 2).putString("endpoint", endpoint)
            .putString("iv", Base64.encodeToString(cipher.iv, Base64.NO_WRAP))
            .putString("token", Base64.encodeToString(encrypted, Base64.NO_WRAP)).commit()) { "Secure storage unavailable" }
    }
    @Synchronized override fun load(): CredentialRead {
        if (prefs.all.isEmpty()) return CredentialRead()
        return try {
            val storedEndpoint = requireNotNull(prefs.getString("endpoint", null))
            val endpoint = BridgeEndpoint.normalize(storedEndpoint)
            val iv = Base64.decode(requireNotNull(prefs.getString("iv", null)), Base64.NO_WRAP)
            val encrypted = Base64.decode(requireNotNull(prefs.getString("token", null)), Base64.NO_WRAP)
            val format = prefs.getInt("format", 1)
            require(iv.size == 12 && encrypted.size in 17..16400 && format in 1..2)
            // Decryption NEVER creates a replacement key for an unreadable record.
            val key = store().getKey(ALIAS, null) as? SecretKey ?: error("Encryption key unavailable")
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(128, iv))
            if (format == 2) cipher.updateAAD(storedEndpoint.toByteArray(Charsets.UTF_8))
            val token = String(cipher.doFinal(encrypted), Charsets.UTF_8)
            require(token.isNotBlank() && token.length <= 4096 && token.none { it == '\r' || it == '\n' })
            if (format == 1) save(endpoint, token)
            CredentialRead(SavedBridge(endpoint, token))
        } catch (_: Exception) {
            clear() // No plaintext fallback or exception/credential logging.
            CredentialRead(unreadable = true)
        }
    }
    @Synchronized override fun clear(): Boolean {
        val removed = try { prefs.edit().clear().commit() } catch (_: Exception) { false }
        val keyRemoved = try { val ks = store(); if (ks.containsAlias(ALIAS)) ks.deleteEntry(ALIAS); true } catch (_: Exception) { false }
        return removed && keyRemoved
    }
    companion object {
        const val PREFERENCES = "tduck_bridge_credentials"
        const val ALIAS = "tduck_companion_bridge_token_v1"
    }
}
