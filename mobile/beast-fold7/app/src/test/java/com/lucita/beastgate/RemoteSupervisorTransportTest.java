package com.lucita.beastgate;

import java.util.concurrent.BlockingQueue;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.function.BooleanSupplier;
import java.util.concurrent.atomic.AtomicLong;
import okhttp3.Response;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;
import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.MockWebServer;
import okhttp3.mockwebserver.RecordedRequest;
import okhttp3.mockwebserver.SocketPolicy;
import okhttp3.tls.HandshakeCertificates;
import okhttp3.tls.HeldCertificate;
import org.json.JSONObject;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import static org.junit.Assert.*;

public class RemoteSupervisorTransportTest {
    private MockWebServer server;
    private RemoteSupervisorTransport sender;
    private final MemoryStore store = new MemoryStore();
    private final BlockingQueue<RemoteSupervisorTransport.Status> statuses = new LinkedBlockingQueue<>();

    static final class MemoryStore implements RemoteSupervisorTransport.CredentialStore {
        volatile RemoteSupervisorTransport.Credential value;
        volatile String thread;
        public RemoteSupervisorTransport.Credential load() { thread = Thread.currentThread().getName(); return value; }
        public void save(RemoteSupervisorTransport.Credential value) { this.value = value; }
        public void clear() { value = null; }
    }

    static final class Peer extends WebSocketListener {
        volatile WebSocket socket;
        final BlockingQueue<String> messages = new LinkedBlockingQueue<>();
        final BlockingQueue<okio.ByteString> images = new LinkedBlockingQueue<>();
        @Override public void onOpen(WebSocket socket, Response response) { this.socket = socket; }
        @Override public void onMessage(WebSocket socket, String text) { messages.add(text); }
        @Override public void onMessage(WebSocket socket, okio.ByteString bytes) { images.add(bytes); }
        @Override public void onClosing(WebSocket socket, int code, String reason) { socket.close(code, reason); }
        String next() throws Exception {
            String value = messages.poll(5, TimeUnit.SECONDS);
            assertNotNull("expected WebSocket message", value);
            return value;
        }
    }

    @Before public void setup() throws Exception {
        server = new MockWebServer(); server.start();
        sender = new RemoteSupervisorTransport(RemoteSupervisorTransport.newClient(), store, true);
    }
    @After public void cleanup() throws Exception { sender.dispose(); server.shutdown(); }
    private String endpoint() { return server.url("/").toString(); }
    private void paired() { store.value = new RemoteSupervisorTransport.Credential(endpoint(), "phone-1", "test-device-secret", System.currentTimeMillis() + 60000); }
    private void start() { sender.start(endpoint(), " Fold7 ", (status, code, expiry) -> statuses.add(status)); }
    private Peer upgrade() {
        Peer peer = new Peer(); server.enqueue(new MockResponse().withWebSocketUpgrade(peer)); return peer;
    }
    private static void await(BooleanSupplier condition) throws Exception {
        long until = System.nanoTime() + TimeUnit.SECONDS.toNanos(6);
        while (!condition.getAsBoolean() && System.nanoTime() < until) Thread.sleep(10);
        assertTrue("condition timed out", condition.getAsBoolean());
    }
    private static String snapshot(int frame) { return "{\"schema\":1,\"running\":true,\"stage\":2,\"frame\":" + frame + "}"; }

    @Test public void authenticationPrecedesReadyAndOnlyLatestStateIsWrapped() throws Exception {
        paired(); Peer peer = upgrade(); start();
        JSONObject auth = new JSONObject(peer.next());
        assertEquals("publisher", auth.getString("role")); assertEquals("test-device-secret", auth.getString("token"));
        sender.offer(snapshot(1)); assertNull(peer.messages.poll(400, TimeUnit.MILLISECONDS));
        peer.socket.send("{\"type\":\"ready\"}"); await(sender::isReady);
        assertNull(peer.messages.poll(300, TimeUnit.MILLISECONDS));
        for (int i = 0; i <= 999; i++) sender.offer(snapshot(i));
        JSONObject wrapper = new JSONObject(peer.next());
        assertEquals(1, wrapper.getInt("protocol")); assertEquals(1, wrapper.getLong("seq"));
        assertFalse(wrapper.getString("stream_id").isEmpty());
        assertTrue(wrapper.getLong("sent_at_ms") > 0);
        assertEquals(999, wrapper.getJSONObject("state").getInt("frame"));
        assertNull(peer.messages.poll(350, TimeUnit.MILLISECONDS));
        RecordedRequest request = server.takeRequest(1, TimeUnit.SECONDS);
        assertEquals("/ws", request.getPath()); assertNull(request.getHeader("Authorization"));
        assertNotEquals(Thread.currentThread().getName(), store.thread);
    }
    @Test public void recordingConsentNeedsVideoAndServerCapabilityAndIsNotRemembered() throws Exception {
        paired(); Peer peer=upgrade(); start(); peer.next();
        peer.socket.send("{\"type\":\"ready\",\"recording_enabled\":true}"); await(sender::isReady);
        sender.setRecordingEnabled(true); sender.offer(snapshot(1));
        assertFalse(new JSONObject(peer.next()).getJSONObject("state").optBoolean("recording_consent"));
        Peer video=upgrade(); sender.setVideoEnabled(true);sender.setRecordingEnabled(true);
        sender.offer(snapshot(2));assertTrue(new JSONObject(peer.next()).getJSONObject("state").getBoolean("recording_consent"));
        video.next();sender.close();
        Peer next=upgrade();start();next.next();next.socket.send("{\"type\":\"ready\",\"recording_enabled\":true}");await(sender::isReady);
        sender.offer(snapshot(3));assertFalse(new JSONObject(next.next()).getJSONObject("state").getBoolean("recording_consent"));
    }
    @Test public void legacyRelayNeverReceivesNewRecordingField() throws Exception {
        paired();Peer peer=upgrade();start();peer.next();peer.socket.send("{\"type\":\"ready\"}");await(sender::isReady);
        sender.setRecordingEnabled(true);sender.offer(snapshot(1));
        assertFalse(new JSONObject(peer.next()).getJSONObject("state").has("recording_consent"));
    }

    @Test public void reauthenticationReconnectsWithoutRewindingStreamOrSequence() throws Exception {
        paired(); Peer first = upgrade(); Peer second = upgrade(); start();
        first.next(); first.socket.send("{\"type\":\"ready\"}"); await(sender::isReady);
        sender.offer(snapshot(1)); JSONObject a = new JSONObject(first.next());
        first.socket.close(4401, "Reauthenticate");
        second.next(); second.socket.send("{\"type\":\"ready\"}"); await(sender::isReady);
        sender.offer(snapshot(2)); JSONObject b = new JSONObject(second.next());
        assertEquals(a.getString("stream_id"), b.getString("stream_id"));
        assertTrue(b.getLong("seq") > a.getLong("seq"));
    }

    @Test public void authenticationUnavailableKeepsCredentialAndReconnectsWithoutPairing() throws Exception {
        paired(); RemoteSupervisorTransport.Credential saved = store.value;
        Peer first = upgrade(); Peer second = upgrade(); start();
        JSONObject firstAuth = new JSONObject(first.next());
        assertEquals("publisher", firstAuth.getString("role"));
        assertEquals("test-device-secret", firstAuth.getString("token"));
        assertFalse(sender.isReady());
        assertTrue(first.socket.close(1013, "Authentication unavailable"));
        await(() -> statuses.contains(RemoteSupervisorTransport.Status.RETRYING));
        assertSame(saved, store.value);

        JSONObject retryAuth = new JSONObject(second.next());
        assertEquals("publisher", retryAuth.getString("role"));
        assertEquals("test-device-secret", retryAuth.getString("token"));
        assertFalse(sender.isReady());
        sender.offer(snapshot(1)); assertNull(second.messages.poll(350, TimeUnit.MILLISECONDS));
        second.socket.send("{\"type\":\"ready\"}"); await(sender::isReady);
        sender.offer(snapshot(2));
        assertEquals(2, new JSONObject(second.next()).getJSONObject("state").getInt("frame"));
        assertSame(saved, store.value);
        for (int i = 0; i < 2; i++) {
            RecordedRequest request = server.takeRequest(1, TimeUnit.SECONDS);
            assertNotNull(request); assertEquals("/ws", request.getPath());
        }
        assertEquals(2, server.getRequestCount());
        assertFalse(statuses.contains(RemoteSupervisorTransport.Status.PAIRING));
        assertFalse(statuses.contains(RemoteSupervisorTransport.Status.CODE));
        assertFalse(statuses.contains(RemoteSupervisorTransport.Status.PAIR_REQUIRED));
        assertFalse(statuses.contains(RemoteSupervisorTransport.Status.ERROR));
    }

    @Test public void revokedCloseClearsCredentialAndNeverRetries() throws Exception {
        paired(); Peer peer = upgrade(); start(); peer.next();
        peer.socket.close(4401, "Revoked");
        await(() -> statuses.contains(RemoteSupervisorTransport.Status.PAIR_REQUIRED));
        assertNull(store.value); assertFalse(sender.isReady());
        server.takeRequest(1, TimeUnit.SECONDS);
        assertNull(server.takeRequest(1600, TimeUnit.MILLISECONDS));
    }

    @Test public void offAndFreshStartCannotBeResumedByOldReady() throws Exception {
        paired(); Peer old = upgrade(); start(); old.next();
        sender.close(); old.socket.send("{\"type\":\"ready\"}"); sender.offer(snapshot(1));
        assertFalse(sender.isReady()); assertNull(old.messages.poll(350, TimeUnit.MILLISECONDS));
        Peer fresh = upgrade(); start(); fresh.next();
        sender.offer(snapshot(2)); assertNull(fresh.messages.poll(350, TimeUnit.MILLISECONDS));
        fresh.socket.send("{\"type\":\"ready\"}"); await(sender::isReady);
        sender.offer(snapshot(3)); assertEquals(3, new JSONObject(fresh.next()).getJSONObject("state").getInt("frame"));
    }

    @Test public void enrollmentUsesNameThenSecretHeaderPollAtTwoSecondIntervals() throws Exception {
        long expiry = System.currentTimeMillis() + 300000;
        server.enqueue(new MockResponse().setBody("{\"code\":\"ABCD2345\",\"poll_token\":\"test-poll-secret\",\"expires_ms\":" + expiry + ",\"interval_ms\":2000}"));
        server.enqueue(new MockResponse().setBody("{\"status\":\"pending\",\"expires_ms\":" + expiry + "}"));
        server.enqueue(new MockResponse().setBody("{\"status\":\"approved\",\"device_id\":\"phone-1\",\"device_token\":\"issued-secret\",\"expires_ms\":" + (expiry + 86400000) + "}"));
        Peer peer = upgrade(); start();
        RecordedRequest request = server.takeRequest(3, TimeUnit.SECONDS);
        assertNotNull(request); assertEquals("POST", request.getMethod()); assertEquals("/pairing/request", request.getPath());
        assertEquals("Fold7", new JSONObject(request.getBody().readUtf8()).getString("name"));
        long firstAt = System.nanoTime();
        RecordedRequest first = server.takeRequest(4, TimeUnit.SECONDS);
        assertTrue(TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - firstAt) >= 1800);
        firstAt = System.nanoTime();
        RecordedRequest second = server.takeRequest(4, TimeUnit.SECONDS);
        assertTrue(TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - firstAt) >= 1800);
        for (RecordedRequest poll : new RecordedRequest[]{first, second}) {
            assertNotNull(poll); assertEquals("POST", poll.getMethod()); assertEquals("/pairing/poll", poll.getPath());
            assertEquals("Bearer test-poll-secret", poll.getHeader("Authorization")); assertEquals(0, poll.getBodySize());
        }
        assertEquals("issued-secret", new JSONObject(peer.next()).getString("token"));
        assertEquals(endpoint(), store.value.endpoint);
        assertTrue(statuses.contains(RemoteSupervisorTransport.Status.CODE));
    }

    @Test public void differentEndpointDoesNotReceivePersistedDeviceToken() throws Exception {
        store.value = new RemoteSupervisorTransport.Credential("https://elsewhere.example/", "phone-1", "do-not-send", System.currentTimeMillis() + 60000);
        server.enqueue(new MockResponse().setResponseCode(410)); start();
        RecordedRequest request = server.takeRequest(3, TimeUnit.SECONDS);
        assertNotNull(request); assertEquals("/pairing/request", request.getPath()); assertNull(request.getHeader("Authorization"));
        assertFalse(request.getBody().readUtf8().contains("do-not-send"));
    }

    @Test public void redirectIsTerminalAndNeverFollowsLocation() throws Exception {
        try (MockWebServer target = new MockWebServer()) {
            target.start(); server.enqueue(new MockResponse().setResponseCode(307).addHeader("Location", target.url("/steal")));
            start(); await(() -> statuses.contains(RemoteSupervisorTransport.Status.ERROR));
            assertEquals(0, target.getRequestCount());
        }
    }

    @Test public void lateEnrollmentResponseAfterCloseDoesNotPollOrSave() throws Exception {
        server.enqueue(new MockResponse().setBody("{\"code\":\"ABCD2345\",\"poll_token\":\"secret\",\"expires_ms\":" + (System.currentTimeMillis() + 300000) + ",\"interval_ms\":2000}").setBodyDelay(1, TimeUnit.SECONDS));
        start(); assertNotNull(server.takeRequest(3, TimeUnit.SECONDS)); sender.close();
        assertNull(server.takeRequest(2500, TimeUnit.MILLISECONDS));
        assertFalse(statuses.contains(RemoteSupervisorTransport.Status.CODE)); assertNull(store.value);
    }

    @Test public void negativeExpiryCannotOverflowIntoAdditionalTime() throws Exception {
        server.enqueue(new MockResponse().setBody("{\"code\":\"ABCD2345\",\"poll_token\":\"secret\",\"expires_ms\":-9223372036854775808,\"interval_ms\":2000}"));
        start();
        assertEquals(RemoteSupervisorTransport.Status.PAIRING, statuses.poll(3, TimeUnit.SECONDS));
        assertEquals(RemoteSupervisorTransport.Status.PAIR_REQUIRED, statuses.poll(3, TimeUnit.SECONDS));
        assertFalse(sender.isReady());
    }

    @Test public void expiredStoredCredentialStopsBeforeAnyNetworkRequest() throws Exception {
        store.value = new RemoteSupervisorTransport.Credential(endpoint(), "device-1", "expired-secret", System.currentTimeMillis() - 1);
        start(); await(() -> statuses.contains(RemoteSupervisorTransport.Status.PAIR_REQUIRED));
        assertNull(store.value); assertEquals(0, server.getRequestCount());
    }

    @Test public void pairingAllowsTwelveMonotonicHoursButCannotOutliveThem() throws Exception {
        sender.dispose(); AtomicLong elapsed = new AtomicLong();
        sender = new RemoteSupervisorTransport(RemoteSupervisorTransport.newClient(), store, true, elapsed::get);
        server.enqueue(new MockResponse().setBody("{\"code\":\"ABCD2345\",\"poll_token\":\"secret\",\"expires_ms\":" + (System.currentTimeMillis() + 86400000) + ",\"interval_ms\":2000}"));
        AtomicLong displayedExpiry = new AtomicLong();
        long before = System.currentTimeMillis();
        sender.start(endpoint(), "Fold7", (status, code, expiry) -> {
            displayedExpiry.set(expiry); statuses.add(status);
        });
        await(() -> statuses.contains(RemoteSupervisorTransport.Status.CODE));
        assertTrue(displayedExpiry.get() >= before + 43199000);
        assertTrue(displayedExpiry.get() <= System.currentTimeMillis() + 43200000);
        elapsed.set(43200000);
        await(() -> statuses.contains(RemoteSupervisorTransport.Status.PAIR_REQUIRED));
        assertEquals(1, server.getRequestCount()); assertNull(store.value);
    }

    @Test public void handshakeUnauthorizedCannotEnterReconnectLoop() throws Exception {
        paired(); server.enqueue(new MockResponse().setResponseCode(401)); start();
        await(() -> statuses.contains(RemoteSupervisorTransport.Status.PAIR_REQUIRED));
        assertNull(store.value); server.takeRequest(1, TimeUnit.SECONDS);
        assertNull(server.takeRequest(1600, TimeUnit.MILLISECONDS));
    }

    @Test public void lostApprovedResponseRetriesSamePollSecretWithoutNewEnrollment() throws Exception {
        long expiry = System.currentTimeMillis() + 300000;
        server.enqueue(new MockResponse().setBody("{\"code\":\"ABCD2345\",\"poll_token\":\"same-secret\",\"expires_ms\":" + expiry + ",\"interval_ms\":2000}"));
        String approved = "{\"status\":\"approved\",\"device_id\":\"device-1\",\"device_token\":\"issued-token\",\"expires_ms\":" + (expiry + 86400000) + "}";
        server.enqueue(new MockResponse().setBody(approved).setSocketPolicy(SocketPolicy.DISCONNECT_DURING_RESPONSE_BODY));
        server.enqueue(new MockResponse().setBody(approved)); Peer peer = upgrade(); start();
        assertNotNull(server.takeRequest(3, TimeUnit.SECONDS));
        RecordedRequest first = server.takeRequest(4, TimeUnit.SECONDS);
        RecordedRequest retry = server.takeRequest(5, TimeUnit.SECONDS);
        assertNotNull(first); assertNotNull(retry);
        assertEquals("/pairing/poll", retry.getPath());
        assertEquals("Bearer same-secret", first.getHeader("Authorization"));
        assertEquals(first.getHeader("Authorization"), retry.getHeader("Authorization"));
        assertEquals("issued-token", new JSONObject(peer.next()).getString("token"));
    }

    @Test public void oversizedResponseFailsClosed() throws Exception {
        server.enqueue(new MockResponse().setBody(" ".repeat(2049))); start();
        await(() -> statuses.contains(RemoteSupervisorTransport.Status.ERROR)); assertNull(store.value);
        server.takeRequest(1, TimeUnit.SECONDS); assertNull(server.takeRequest(1200, TimeUnit.MILLISECONDS));
    }

    @Test public void untrustedTlsCertificateIsRejectedWithoutRetryOrCredentials() throws Exception {
        sender.dispose();
        java.util.concurrent.atomic.AtomicReference<Exception> failure = new java.util.concurrent.atomic.AtomicReference<>();
        var client = RemoteSupervisorTransport.newClient().newBuilder().eventListener(new okhttp3.EventListener() {
            @Override public void callFailed(okhttp3.Call call, java.io.IOException error) { failure.set(error); }
        }).build();
        sender = new RemoteSupervisorTransport(client, store, true);
        HeldCertificate certificate = new HeldCertificate.Builder().addSubjectAlternativeName("127.0.0.1").build();
        HandshakeCertificates certificates = new HandshakeCertificates.Builder().heldCertificate(certificate).build();
        try (MockWebServer secure = new MockWebServer()) {
            secure.useHttps(certificates.sslSocketFactory(), false); secure.start();
            // Use the actual IPv4 bind, not localhost's unrelated IPv6 fallback failure.
            sender.start(secure.url("/").newBuilder().host("127.0.0.1").build().toString(), "Fold7", (status, code, expiry) -> statuses.add(status));
            assertEquals(RemoteSupervisorTransport.Status.PAIRING, statuses.poll(3, TimeUnit.SECONDS));
            RemoteSupervisorTransport.Status result = statuses.poll(15, TimeUnit.SECONDS);
            assertEquals(String.valueOf(failure.get()), RemoteSupervisorTransport.Status.ERROR, result);
            assertTrue(failure.get() instanceof javax.net.ssl.SSLException);
            assertNull(store.value); assertFalse(sender.isReady()); assertEquals(0, secure.getRequestCount());
        }
    }

    @Test public void repeatedServerDisconnectKeepsEnrollmentAndDiscardsOfflineSnapshots() throws Exception {
        paired(); RemoteSupervisorTransport.Credential saved = store.value;
        Peer peer = upgrade(); start(); peer.next(); peer.socket.send("{\"type\":\"ready\"}"); await(sender::isReady);
        String stream = null; long sequence = 0;
        for (int i = 1; i <= 5; i++) {
            sender.offer(snapshot(i)); JSONObject message = new JSONObject(peer.next());
            if (stream == null) stream = message.getString("stream_id");
            assertEquals(stream, message.getString("stream_id"));
            assertTrue(message.getLong("seq") > sequence); sequence = message.getLong("seq");
            assertEquals(i, message.getJSONObject("state").getInt("frame"));
            Peer next = upgrade(); peer.socket.close(1001, "Server restart"); await(() -> !sender.isReady());
            sender.offer(snapshot(9000));
            assertEquals("test-device-secret", new JSONObject(next.next()).getString("token"));
            next.socket.send("{\"type\":\"ready\"}"); await(sender::isReady);
            assertNull(next.messages.poll(300, TimeUnit.MILLISECONDS));
            assertSame(saved, store.value); peer = next;
        }
        assertFalse(statuses.contains(RemoteSupervisorTransport.Status.PAIR_REQUIRED));
        assertFalse(statuses.contains(RemoteSupervisorTransport.Status.ERROR));
    }

    @Test public void freshTransportRestoresCredentialWithoutPairing() throws Exception {
        paired(); Peer first = upgrade(); start(); first.next();
        first.socket.send("{\"type\":\"ready\"}"); await(sender::isReady);
        sender.offer(snapshot(1)); String oldStream = new JSONObject(first.next()).getString("stream_id");
        sender.dispose();
        sender = new RemoteSupervisorTransport(RemoteSupervisorTransport.newClient(), store, true);
        Peer fresh = upgrade(); start();
        assertEquals("test-device-secret", new JSONObject(fresh.next()).getString("token"));
        fresh.socket.send("{\"type\":\"ready\"}"); await(sender::isReady);sender.offer(snapshot(2));
        JSONObject message = new JSONObject(fresh.next());
        assertNotEquals(oldStream, message.getString("stream_id"));assertEquals(1, message.getLong("seq"));
        assertEquals(2, message.getJSONObject("state").getInt("frame"));
        assertFalse(statuses.contains(RemoteSupervisorTransport.Status.PAIRING));
    }

    @Test public void stoppingDuringRetryPreventsBackgroundReconnect() throws Exception {
        paired(); Peer first = upgrade(); start(); first.next();
        first.socket.send("{\"type\":\"ready\"}"); await(sender::isReady);
        first.socket.close(1001, "Server restart");await(() -> statuses.contains(RemoteSupervisorTransport.Status.RETRYING));
        sender.close();int requests = server.getRequestCount();
        Thread.sleep(1800);assertEquals(requests, server.getRequestCount());
        assertNotNull(store.value);assertFalse(sender.isReady());
    }

    @Test public void disposeCannotBeRestarted() throws Exception {
        sender.dispose(); start(); sender.offer(snapshot(1));
        Thread.sleep(300); assertEquals(0, server.getRequestCount()); assertFalse(sender.isReady());
    }

    @Test public void videoNeedsFreshConsentAndSeparateAuthenticatedSocket() throws Exception {
        paired();Peer state=upgrade();start();state.next();state.socket.send("{\"type\":\"ready\"}");await(sender::isReady);
        sender.offer(snapshot(1));assertFalse(new JSONObject(state.next()).getJSONObject("state").getBoolean("video_available"));
        assertFalse(sender.canSendVideo());assertEquals(1,server.getRequestCount());
        Peer video=upgrade();sender.setVideoEnabled(true);
        assertEquals("test-device-secret",new JSONObject(video.next()).getString("token"));
        assertFalse(sender.canSendVideo());
        video.socket.send("{\"type\":\"ready\"}");await(sender::canSendVideo);
        byte[] image={-1,-40,-1,-39};sender.offerVideo(image);
        assertArrayEquals(image,video.images.poll(2,TimeUnit.SECONDS).toByteArray());
        sender.offer(snapshot(2));assertTrue(new JSONObject(state.next()).getJSONObject("state").getBoolean("video_available"));
        assertEquals("/ws",server.takeRequest(1,TimeUnit.SECONDS).getPath());
        assertEquals("/video",server.takeRequest(1,TimeUnit.SECONDS).getPath());
        sender.setVideoEnabled(false);assertFalse(sender.canSendVideo());assertTrue(sender.isReady());
        sender.offerVideo(image);assertNull(video.images.poll(300,TimeUnit.MILLISECONDS));
        sender.offer(snapshot(3));assertFalse(new JSONObject(state.next()).getJSONObject("state").getBoolean("video_available"));
        sender.close();Peer next=upgrade();start();next.next();next.socket.send("{\"type\":\"ready\"}");await(sender::isReady);
        assertFalse(sender.canSendVideo());sender.offer(snapshot(4));assertFalse(new JSONObject(next.next()).getJSONObject("state").getBoolean("video_available"));
    }

    @Test public void mediaFailureDoesNotInterruptStateOrClearCredential() throws Exception {
        paired();Peer state=upgrade();Peer video=upgrade();start();sender.setVideoEnabled(true);
        state.next();state.socket.send("{\"type\":\"ready\"}");await(sender::isReady);
        video.next();video.socket.send("{\"type\":\"ready\"}");await(sender::canSendVideo);
        video.socket.close(1013,"Video unavailable");await(()->!sender.canSendVideo());
        sender.offer(snapshot(12));assertEquals(12,new JSONObject(state.next()).getJSONObject("state").getInt("frame"));
        assertTrue(sender.isReady());assertNotNull(store.value);
    }
}
