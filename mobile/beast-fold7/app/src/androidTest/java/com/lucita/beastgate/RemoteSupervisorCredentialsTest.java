package com.lucita.beastgate;

import android.content.Context;
import androidx.test.platform.app.InstrumentationRegistry;
import java.security.KeyStore;
import javax.crypto.SecretKey;
import android.security.keystore.KeyInfo;
import javax.crypto.SecretKeyFactory;
import org.junit.Test;
import static org.junit.Assert.*;

public class RemoteSupervisorCredentialsTest {
    @Test public void keystoreRoundTripBindsEndpointAndNeverStoresPlaintextToken() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        String namespace = "remote-supervisor-test-" + java.util.UUID.randomUUID();
        RemoteSupervisorCredentials store = new RemoteSupervisorCredentials(context, namespace);
        try {
            assertNull(store.load());
            store.save(new RemoteSupervisorTransport.Credential("https://relay.example/", "device-1", "sensitive-device-token", System.currentTimeMillis() + 60000));
            RemoteSupervisorTransport.Credential restored = new RemoteSupervisorCredentials(context, namespace).load();
            assertEquals("https://relay.example/", restored.endpoint);
            assertEquals("sensitive-device-token", restored.token);
            String disk = context.getSharedPreferences(namespace, Context.MODE_PRIVATE).getAll().toString();
            assertFalse(disk.contains("sensitive-device-token")); assertFalse(disk.contains("device-1"));
            KeyStore keys = KeyStore.getInstance("AndroidKeyStore"); keys.load(null);
            SecretKey key = (SecretKey) keys.getKey(namespace, null);
            assertNull(key.getEncoded());
            KeyInfo info = (KeyInfo) SecretKeyFactory.getInstance(key.getAlgorithm(), "AndroidKeyStore").getKeySpec(key, KeyInfo.class);
            assertArrayEquals(new String[]{"GCM"}, info.getBlockModes());
            context.getSharedPreferences(namespace, Context.MODE_PRIVATE).edit().putString("endpoint", "https://attacker.example/").commit();
            assertThrows(Exception.class, store::load);
            store.clear(); assertNull(store.load());
        } finally {
            store.clear(); KeyStore keys = KeyStore.getInstance("AndroidKeyStore"); keys.load(null); keys.deleteEntry(namespace);
        }
    }

    @Test public void mainThreadCannotPerformCredentialIo() {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        RemoteSupervisorCredentials store = new RemoteSupervisorCredentials(context, "unused-main-thread-test");
        InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> assertThrows(IllegalStateException.class, store::load));
    }
}
