package com.lucita.beastgate;

import org.junit.Test;
import static org.junit.Assert.*;

public class RemoteSupervisorPolicyTest {
    @Test public void onlyHttpsOriginsOrExplicitDebugLoopbackAreAccepted() {
        assertEquals("https://relay.example/", RemoteSupervisorPolicy.endpoint("https://relay.example", false));
        assertEquals("http://127.0.0.1:8767/", RemoteSupervisorPolicy.endpoint("http://127.0.0.1:8767", true));
        assertEquals("http://localhost:8767/", RemoteSupervisorPolicy.endpoint("http://localhost:8767/", true));
        for (String input : new String[]{"http://relay.example", "http://192.168.0.1", "http://127.1",
                "http://localhost.evil", "https://user:pass@relay.example", "https://@relay.example",
                "https://relay.example/ws", "https://relay.example/a/..", "https://relay.example/?key=x",
                "https://relay.example/#x", "https://relay.example?", "https://relay.example#",
                "wss://relay.example", "https://relay.example\\evil", "https://relay.example:0", ""}) {
            assertThrows(input, IllegalArgumentException.class, () -> RemoteSupervisorPolicy.endpoint(input, true));
        }
        assertThrows(IllegalArgumentException.class, () -> RemoteSupervisorPolicy.endpoint("http://localhost", false));
        assertThrows(IllegalArgumentException.class, () -> RemoteSupervisorPolicy.endpoint("http://127.0.0.1", false));
    }

    @Test public void namesAreTrimmedAndBoundedBeforeEnrollment() {
        assertEquals("Fold7", RemoteSupervisorPolicy.name("  Fold7  "));
        assertThrows(IllegalArgumentException.class, () -> RemoteSupervisorPolicy.name("   "));
        assertThrows(IllegalArgumentException.class, () -> RemoteSupervisorPolicy.name("x".repeat(65)));
    }

    @Test public void onlyExplicitReauthenticationCanRetryUnauthorizedClose() {
        assertTrue(RemoteSupervisorPolicy.mayReconnect(4401, "Reauthenticate"));
        assertFalse(RemoteSupervisorPolicy.mayReconnect(4401, "Revoked"));
        assertFalse(RemoteSupervisorPolicy.mayReconnect(4401, "reauthenticate"));
        assertFalse(RemoteSupervisorPolicy.mayReconnect(4403, "Forbidden"));
        assertTrue(RemoteSupervisorPolicy.mayReconnect(1006, ""));
    }

    @Test public void retryJitterNeverExceedsOneToThirtySeconds() {
        for (int attempt = 0; attempt < 100; attempt++) {
            for (double jitter : new double[]{0, .5, .999999}) {
                long delay = RemoteSupervisorPolicy.retryMillis(attempt, jitter);
                assertTrue(delay >= 1000);
                assertTrue(delay <= 30000);
            }
        }
        assertTrue(RemoteSupervisorPolicy.retryMillis(3, .8) > RemoteSupervisorPolicy.retryMillis(0, .8));
        assertNotEquals(RemoteSupervisorPolicy.retryMillis(3, .1), RemoteSupervisorPolicy.retryMillis(3, .9));
    }

    @Test public void runningSamplingIsAtMostFourHertzAndIdleIsOneHertz() {
        assertEquals(250, RemoteSupervisorPolicy.sampleMillis(true));
        assertEquals(1000, RemoteSupervisorPolicy.sampleMillis(false));
    }
}
