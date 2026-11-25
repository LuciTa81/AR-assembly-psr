package com.lucita.beastgate;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Looper;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import org.json.JSONObject;

/** Keystore key is non-exportable; the endpoint is authenticated as AES-GCM AAD. */
final class RemoteSupervisorCredentials implements RemoteSupervisorTransport.CredentialStore {
    private final Context context;
    private final String namespace;

    RemoteSupervisorCredentials(Context context) { this(context, "remote-supervisor-v1"); }
    RemoteSupervisorCredentials(Context context, String namespace) {
        this.context = context.getApplicationContext(); this.namespace = namespace;
    }

    private SharedPreferences preferences() {
        if (Looper.myLooper() == Looper.getMainLooper()) throw new IllegalStateException("Credential I/O must run off the main thread");
        return context.getSharedPreferences(namespace, Context.MODE_PRIVATE);
    }

    private SecretKey key(boolean create) throws Exception {
        KeyStore keys = KeyStore.getInstance("AndroidKeyStore"); keys.load(null);
        SecretKey existing = (SecretKey) keys.getKey(namespace, null);
        if (existing != null) return existing;
        if (!create) throw new IOException("Credential key unavailable");
        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(namespace, KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setKeySize(256).setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).setRandomizedEncryptionRequired(true).build());
        return generator.generateKey();
    }

    @Override public RemoteSupervisorTransport.Credential load() throws Exception {
        SharedPreferences preferences = preferences();
        String ciphertext = preferences.getString("ciphertext", null);
        if (ciphertext == null) return null;
        String endpoint = preferences.getString("endpoint", "");
        byte[] nonce = Base64.decode(preferences.getString("nonce", ""), Base64.NO_WRAP);
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, key(false), new GCMParameterSpec(128, nonce));
        cipher.updateAAD(endpoint.getBytes(StandardCharsets.UTF_8));
        byte[] plain = cipher.doFinal(Base64.decode(ciphertext, Base64.NO_WRAP));
        try {
            JSONObject json = new JSONObject(new String(plain, StandardCharsets.UTF_8));
            return new RemoteSupervisorTransport.Credential(endpoint, json.getString("device_id"), json.getString("token"), json.getLong("expires_ms"));
        } finally { java.util.Arrays.fill(plain, (byte) 0); }
    }

    @Override public void save(RemoteSupervisorTransport.Credential value) throws Exception {
        SharedPreferences preferences = preferences();
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, key(true));
        cipher.updateAAD(value.endpoint.getBytes(StandardCharsets.UTF_8));
        byte[] plain = new JSONObject().put("device_id", value.deviceId).put("token", value.token)
                .put("expires_ms", value.expiresMs).toString().getBytes(StandardCharsets.UTF_8);
        byte[] encrypted;
        try { encrypted = cipher.doFinal(plain); }
        finally { java.util.Arrays.fill(plain, (byte) 0); }
        boolean saved = preferences.edit().clear().putString("endpoint", value.endpoint)
                .putString("nonce", Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP))
                .putString("ciphertext", Base64.encodeToString(encrypted, Base64.NO_WRAP)).commit();
        if (!saved) throw new IOException("Credential persistence failed");
    }

    @Override public void clear() throws IOException {
        if (!preferences().edit().clear().commit()) throw new IOException("Credential removal failed");
    }
}
