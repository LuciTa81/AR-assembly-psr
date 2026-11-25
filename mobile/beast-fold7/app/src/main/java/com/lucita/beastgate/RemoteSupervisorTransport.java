package com.lucita.beastgate;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.ScheduledThreadPoolExecutor;
import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.Consumer;
import java.util.function.LongSupplier;
import javax.net.ssl.SSLException;
import okhttp3.Call;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;
import okio.ByteString;
import org.json.JSONObject;

/** No Android dependencies: all disk, encryption, HTTP and serialization run on the worker. */
final class RemoteSupervisorTransport {
    enum Status { PAIRING, CODE, CONNECTING, CONNECTED, RETRYING, PAIR_REQUIRED, ERROR }
    interface Listener { void changed(Status status, String code, long expiresMs); }
    interface CredentialStore {
        Credential load() throws Exception;
        void save(Credential value) throws Exception;
        void clear() throws Exception;
    }
    static final class Credential {
        final String endpoint, deviceId, token;
        final long expiresMs;
        Credential(String endpoint, String deviceId, String token, long expiresMs) {
            this.endpoint = endpoint; this.deviceId = deviceId; this.token = token; this.expiresMs = expiresMs;
        }
    }

    private static final int MAX_STATE_BYTES = 16384;
    private static final long PAIRING_LIFETIME_MS = 12 * 60 * 60 * 1000;
    private final OkHttpClient client;
    private final CredentialStore store;
    private final boolean debug;
    private final LongSupplier elapsedMillis;
    private final Object gate = new Object();
    private final ScheduledThreadPoolExecutor worker = new ScheduledThreadPoolExecutor(1, runnable -> {
        Thread thread = new Thread(runnable, "remote-supervisor"); thread.setDaemon(true); return thread;
    });
    private Session active;
    private boolean disposed;

    private static final class Session {
        final String endpoint, name, stream = UUID.randomUUID().toString();
        final Listener listener;
        final AtomicReference<String> latest = new AtomicReference<>();
        long sequence, due, pairingDeadline, expiresMs;
        String pollToken, code = "";
        int attempts;
        boolean loaded, stopped;
        Credential credential;
        Connection connection,videoConnection;
        boolean videoEnabled, recordingEnabled;
        long videoRetryAt;
        Call call;
        ScheduledFuture<?> task;
        Status status;
        Session(String endpoint, String name, Listener listener, long now) {
            this.endpoint = endpoint; this.name = name; this.listener = listener;
            pairingDeadline = now + PAIRING_LIFETIME_MS;
        }
    }
    private static final class Connection {
        final AtomicReference<Disconnect> ended = new AtomicReference<>();
        volatile boolean ready;
        boolean recordingAvailable;
        WebSocket socket;
        final long deadline;
        long queuedSince;
        boolean announced;
        Connection(long now) { deadline = now + 10000; }
    }
    private static final class Disconnect {
        final boolean unauthorized, fatal;
        Disconnect(boolean unauthorized, boolean fatal) { this.unauthorized = unauthorized; this.fatal = fatal; }
    }
    private static final class HttpFailure extends IOException {
        final int code;
        HttpFailure(int code) { super("Relay HTTP failure"); this.code = code; }
    }

    static OkHttpClient newClient() {
        return new OkHttpClient.Builder().followRedirects(false).followSslRedirects(false)
                .retryOnConnectionFailure(false).connectTimeout(10, TimeUnit.SECONDS)
                .readTimeout(10, TimeUnit.SECONDS).writeTimeout(10, TimeUnit.SECONDS)
                .callTimeout(12, TimeUnit.SECONDS).pingInterval(20, TimeUnit.SECONDS).build();
    }

    RemoteSupervisorTransport(OkHttpClient client, CredentialStore store, boolean debug) {
        this(client, store, debug, () -> TimeUnit.NANOSECONDS.toMillis(System.nanoTime()));
    }

    RemoteSupervisorTransport(OkHttpClient client, CredentialStore store, boolean debug, LongSupplier elapsedMillis) {
        this.client = client; this.store = store; this.debug = debug;
        this.elapsedMillis = elapsedMillis;
        if (client.followRedirects() || client.followSslRedirects()) throw new IllegalArgumentException("Redirects must be disabled");
        worker.setRemoveOnCancelPolicy(true);
        worker.setExecuteExistingDelayedTasksAfterShutdownPolicy(false);
        worker.setContinueExistingPeriodicTasksAfterShutdownPolicy(false);
    }

    void loadEndpoint(Consumer<String> result) {
        synchronized (gate) {
            if (disposed) return;
            worker.execute(() -> {
                String endpoint = "";
                try { Credential saved = store.load(); if (saved != null) endpoint = RemoteSupervisorPolicy.endpoint(saved.endpoint, debug); }
                catch (Exception ignored) { /* Enrollment can replace unreadable credentials. */ }
                synchronized (gate) { if (!disposed) result.accept(endpoint); }
            });
        }
    }

    void start(String endpoint, String name, Listener listener) {
        Session session = new Session(RemoteSupervisorPolicy.endpoint(endpoint, debug), RemoteSupervisorPolicy.name(name), listener, now());
        synchronized (gate) {
            if (disposed) return;
            closeLocked(); active = session;
            // One periodic task per active generation; callbacks never enqueue worker tasks.
            session.task = worker.scheduleWithFixedDelay(() -> tick(session), 0, 250, TimeUnit.MILLISECONDS);
        }
    }

    boolean isReady() {
        synchronized (gate) { return active != null && live(active) && ready(active.connection); }
    }

    void offer(String snapshot) {
        if (snapshot == null || snapshot.length() > MAX_STATE_BYTES) return;
        synchronized (gate) {
            if (active != null && live(active) && ready(active.connection)) active.latest.set(snapshot);
        }
    }

    void setVideoEnabled(boolean enabled) {
        synchronized(gate){
            if(active==null||!live(active))return;
            active.videoEnabled=enabled;
            if(!enabled){active.recordingEnabled=false;disconnectVideo(active);}
        }
    }
    void setRecordingEnabled(boolean enabled){
        synchronized(gate){if(active!=null&&live(active))active.recordingEnabled=enabled&&active.videoEnabled;}
    }
    boolean recordingAvailable(){
        synchronized(gate){return active!=null&&ready(active.connection)&&active.connection.recordingAvailable;}
    }
    boolean canSendVideo(){
        synchronized(gate){return active!=null&&live(active)&&active.videoEnabled&&ready(active.connection)
            &&ready(active.videoConnection)&&active.videoConnection.socket.queueSize()==0;}
    }
    boolean offerVideo(byte[] jpeg){
        if(jpeg==null||jpeg.length>AvcPacket.MAX_BYTES||jpeg.length<4)return false;
        synchronized(gate){
            if(!canSendVideo())return false;
            Connection connection=active.videoConnection;
            boolean accepted=connection.socket.send(ByteString.of(jpeg));
            if(!accepted)connection.ended.compareAndSet(null,new Disconnect(false,false));
            return accepted;
        }
    }

    private static boolean ready(Connection connection) {
        return connection != null && connection.ready && connection.ended.get() == null;
    }
    private boolean live(Session session) { return !disposed && active == session && !session.stopped; }
    private boolean current(Session session) { synchronized (gate) { return live(session); } }
    private long now() { return elapsedMillis.getAsLong(); }

    private void tick(Session session) {
        if (!current(session)) return;
        try {
            if (!session.loaded) {
                Credential saved;
                try { saved = store.load(); }
                catch (Exception unreadable) { store.clear(); saved = null; }
                if (!current(session)) return;
                if (saved != null && session.endpoint.equals(saved.endpoint)) session.credential = saved;
                session.loaded = true;
            }
            if (session.credential == null && now() >= session.pairingDeadline) { finish(session, Status.PAIR_REQUIRED, false); return; }
            if (session.credential != null && session.credential.expiresMs <= System.currentTimeMillis()) {
                finish(session, Status.PAIR_REQUIRED, true); return;
            }
            if (now() < session.due) return;
            if (session.credential == null) { pair(session); return; }
            if (session.connection == null) { connect(session); return; }
            Connection connection = session.connection;
            Disconnect ended = connection.ended.get();
            if (ended != null) {
                if (ended.unauthorized) finish(session, Status.PAIR_REQUIRED, true);
                else if (ended.fatal) finish(session, Status.ERROR, false);
                else retry(session);
                return;
            }
            if (!connection.ready) {
                if (now() >= connection.deadline) retry(session);
                return;
            }
            if (!connection.announced) {
                connection.announced = true; session.attempts = 0; emit(session, Status.CONNECTED);
            }
            publish(session, connection);
            synchronized(gate){
                if(!live(session)||!session.videoEnabled)return;
                Connection video=session.videoConnection;
                if(video!=null&&video.socket.queueSize()!=0){
                    if(video.queuedSince==0)video.queuedSince=now();
                    if(now()-video.queuedSince>=3000)video.ended.compareAndSet(null,new Disconnect(false,false));
                }else if(video!=null)video.queuedSince=0;
                if(video!=null&&(video.ended.get()!=null||(!video.ready&&now()>=video.deadline))){
                    disconnectVideo(session);session.videoRetryAt=now()+5000;
                }
                if(session.videoConnection==null&&now()>=session.videoRetryAt)connect(session,true);
            }
        } catch (HttpFailure error) {
            if (error.code == 401 || error.code == 403 || error.code == 410) finish(session, Status.PAIR_REQUIRED, true);
            else if (error.code == 408 || error.code == 429 || error.code >= 500) retry(session);
            else finish(session, Status.ERROR, false);
        } catch (SSLException error) {
            finish(session, Status.ERROR, false);
        } catch (IOException error) {
            retry(session);
        } catch (Exception error) {
            finish(session, Status.ERROR, false);
        }
    }

    private void pair(Session session) throws Exception {
        if (session.pollToken == null) {
            emit(session, Status.PAIRING);
            JSONObject response = post(session, "pairing/request", new JSONObject().put("name", session.name).toString(), null);
            if (!current(session)) return;
            String code = response.getString("code");
            if (!code.matches("[A-HJ-NP-Z2-9]{8}") || response.getLong("interval_ms") != 2000) throw new IllegalArgumentException("Invalid pairing response");
            session.pollToken = secret(response.getString("poll_token")); session.code = code;
            limitPairingExpiry(session, response.getLong("expires_ms"));
            if (now() >= session.pairingDeadline) { finish(session, Status.PAIR_REQUIRED, false); return; }
            session.attempts = 0; session.due = now() + 2000; emit(session, Status.CODE);
            return;
        }
        JSONObject response = post(session, "pairing/poll", null, session.pollToken);
        if (!current(session)) return;
        if (now() >= session.pairingDeadline) { finish(session, Status.PAIR_REQUIRED, false); return; }
        String status = response.getString("status");
        if (status.equals("pending")) {
            limitPairingExpiry(session, response.getLong("expires_ms"));
            session.attempts = 0; session.due = now() + 2000; emit(session, Status.CODE);
        } else if (status.equals("approved")) {
            String id = response.getString("device_id");
            long expiry = response.getLong("expires_ms");
            if (id.isEmpty() || id.length() > 128 || expiry <= System.currentTimeMillis()) throw new IllegalArgumentException("Invalid credential response");
            Credential credential = new Credential(session.endpoint, id, secret(response.getString("device_token")), expiry);
            store.save(credential);
            if (!current(session)) return;
            session.credential = credential; session.pollToken = null; session.code = ""; session.due = 0; session.attempts = 0;
        } else throw new IllegalArgumentException("Invalid pairing status");
    }

    private void limitPairingExpiry(Session session, long expiresMs) {
        long wallNow = System.currentTimeMillis();
        long remaining = expiresMs <= wallNow ? 0 : Math.min(PAIRING_LIFETIME_MS, expiresMs - wallNow);
        session.expiresMs = wallNow + Math.min(remaining, Math.max(0, session.pairingDeadline - now()));
        session.pairingDeadline = Math.min(session.pairingDeadline, now() + remaining);
    }

    private static String secret(String value) {
        if (!value.matches("[A-Za-z0-9._~-]{1,512}")) throw new IllegalArgumentException("Invalid credential");
        return value;
    }

    private JSONObject post(Session session, String path, String json, String token) throws Exception {
        Request.Builder request = new Request.Builder().url(session.endpoint + path)
                .post(RequestBody.create(json == null ? "" : json, json == null ? null : MediaType.get("application/json")));
        if (token != null) request.header("Authorization", "Bearer " + token);
        Call call = client.newCall(request.build());
        synchronized (gate) { if (!live(session)) throw new IOException("Stopped"); session.call = call; }
        try (Response response = call.execute()) {
            if (!response.isSuccessful()) throw new HttpFailure(response.code());
            if (response.body() == null) throw new IllegalArgumentException("Empty response");
            byte[] bytes = response.body().byteStream().readNBytes(2049);
            if (bytes.length > 2048) throw new IllegalArgumentException("Oversize response");
            return new JSONObject(new String(bytes, StandardCharsets.UTF_8));
        } finally {
            synchronized (gate) { if (session.call == call) session.call = null; }
        }
    }

    private void connect(Session session) throws Exception {
        connect(session,false);
    }
    private void connect(Session session, boolean video) throws Exception {
        if(!video)emit(session, Status.CONNECTING);
        Connection connection = new Connection(now());
        String authentication = new JSONObject().put("role", "publisher").put("token", session.credential.token).toString();
        Request request = new Request.Builder().url(session.endpoint + (video?"video":"ws")).build();
        synchronized (gate) {
            if (!live(session)) return;
            if(video)session.videoConnection=connection;
            else{session.latest.set(null);session.connection=connection;}
            connection.socket = client.newWebSocket(request, new WebSocketListener() {
                private boolean valid() { return live(session) && (video?session.videoConnection:session.connection) == connection && connection.ended.get() == null; }
                @Override public void onOpen(WebSocket socket, Response response) {
                    synchronized (gate) {
                        if (!valid()) { socket.cancel(); return; }
                        if (!socket.send(authentication)) connection.ended.compareAndSet(null, new Disconnect(false, false));
                    }
                }
                @Override public void onMessage(WebSocket socket, String text) {
                    synchronized (gate) {
                        if (!valid()) return;
                        try {
                            if (text.length() > 2048)throw new IllegalArgumentException("Oversize relay message");
                            JSONObject message=new JSONObject(text);
                            if (!"ready".equals(message.optString("type")))
                                throw new IllegalArgumentException("Unexpected relay message");
                            connection.recordingAvailable=message.optBoolean("recording_enabled",false);
                            connection.ready = true;
                        } catch (Exception error) { connection.ended.compareAndSet(null, new Disconnect(false, true)); }
                    }
                }
                @Override public void onMessage(WebSocket socket, ByteString bytes) {
                    connection.ended.compareAndSet(null, new Disconnect(false, true));
                }
                @Override public void onClosing(WebSocket socket, int code, String reason) {
                    connection.ended.compareAndSet(null, new Disconnect(!RemoteSupervisorPolicy.mayReconnect(code, reason), false));
                    socket.close(code, reason);
                }
                @Override public void onClosed(WebSocket socket, int code, String reason) {
                    connection.ended.compareAndSet(null, new Disconnect(!RemoteSupervisorPolicy.mayReconnect(code, reason), false));
                }
                @Override public void onFailure(WebSocket socket, Throwable error, Response response) {
                    int code = response == null ? 0 : response.code();
                    boolean unauthorized = code == 401 || code == 403 || code == 410;
                    boolean fatal = error instanceof SSLException || (code > 0 && code != 408 && code != 429 && code < 500);
                    connection.ended.compareAndSet(null, new Disconnect(unauthorized, fatal));
                    if (response != null) response.close();
                }
            });
        }
    }

    private void publish(Session session, Connection connection) throws Exception {
        if (connection.socket.queueSize() != 0) {
            if (connection.queuedSince == 0) connection.queuedSince = now();
            if (now() - connection.queuedSince >= 5000) retry(session);
            return;
        }
        connection.queuedSince = 0;
        String latest = session.latest.getAndSet(null);
        if (latest == null) return;
        JSONObject state=new JSONObject(latest);
        synchronized(gate){
            state.put("video_available",session.videoEnabled&&state.optBoolean("running"));
            state.remove("recording_consent");
            if(connection.recordingAvailable)state.put("recording_consent",session.recordingEnabled&&session.videoEnabled&&state.optBoolean("running"));
        }
        String message = new JSONObject().put("protocol", 1).put("stream_id", session.stream)
                .put("seq", ++session.sequence).put("sent_at_ms", System.currentTimeMillis())
                .put("state", state).toString();
        if (message.getBytes(StandardCharsets.UTF_8).length > MAX_STATE_BYTES) throw new IllegalArgumentException("Oversize state");
        synchronized (gate) {
            if (live(session) && session.connection == connection && ready(connection) && !connection.socket.send(message))
                connection.ended.compareAndSet(null, new Disconnect(false, false));
        }
    }

    private void retry(Session session) {
        synchronized (gate) {
            if (!live(session)) return;
            disconnect(session);
            long delay = RemoteSupervisorPolicy.retryMillis(session.attempts++, ThreadLocalRandom.current().nextDouble());
            if (session.pollToken != null) delay = Math.max(2000, delay);
            session.due = now() + delay; emit(session, Status.RETRYING);
        }
    }

    private void finish(Session session, Status status, boolean clearCredential) {
        synchronized (gate) {
            if (!live(session)) return;
            session.stopped = true; disconnect(session);
            if (session.task != null) session.task.cancel(false);
        }
        if (clearCredential) {
            try {
                Credential saved = store.load();
                if (saved != null && session.endpoint.equals(saved.endpoint)) store.clear();
            } catch (Exception ignored) { /* Remain stopped even when secure storage is unavailable. */ }
        }
        synchronized (gate) {
            if (active == session && !disposed) session.listener.changed(status, "", 0);
        }
    }

    private void emit(Session session, Status status) {
        synchronized (gate) {
            if (live(session) && session.status != status) {
                session.status = status; session.listener.changed(status, session.code, session.expiresMs);
            }
        }
    }

    private void disconnect(Session session) {
        disconnectVideo(session);
        if (session.connection != null) {
            session.connection.socket.cancel(); session.connection = null;
        }
        session.latest.set(null);
    }

    private void disconnectVideo(Session session){
        if(session.videoConnection!=null){session.videoConnection.socket.cancel();session.videoConnection=null;}
    }

    private void closeLocked() {
        if (active == null) return;
        Session session = active; active = null; session.stopped = true;
        if (session.task != null) session.task.cancel(false);
        if (session.call != null) session.call.cancel();
        disconnect(session);
    }
    void close() { synchronized (gate) { closeLocked(); } }
    void dispose() {
        synchronized (gate) {
            if (disposed) return;
            disposed = true; closeLocked(); worker.shutdownNow();
        }
        client.dispatcher().cancelAll(); client.connectionPool().evictAll(); client.dispatcher().executorService().shutdown();
    }
}
