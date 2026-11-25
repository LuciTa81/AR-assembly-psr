package com.lucita.beastgate;

import android.os.Handler;
import android.os.Looper;
import java.util.function.BooleanSupplier;
import java.util.function.Consumer;
import java.util.function.Supplier;
import org.json.JSONObject;

final class RemoteSupervisorSampler {
    private final Handler main = new Handler(Looper.getMainLooper());
    private final Supplier<String> state;
    private final BooleanSupplier ready;
    private final Consumer<String> sink;
    private boolean active;

    RemoteSupervisorSampler(Supplier<String> state, BooleanSupplier ready, Consumer<String> sink) {
        this.state = state; this.ready = ready; this.sink = sink;
    }

    private final Runnable sample = new Runnable() {
        @Override public void run() {
            if (!active) return;
            long delay = 250;
            if (ready.getAsBoolean()) {
                try {
                    String snapshot = state.get();
                    delay = RemoteSupervisorPolicy.sampleMillis(new JSONObject(snapshot).getBoolean("running"));
                    sink.accept(snapshot);
                } catch (Exception failure) {
                    close(); sink.accept(null); return;
                }
            }
            if (active) main.postDelayed(this, delay);
        }
    };

    void start() { close(); active = true; main.post(sample); }
    void close() {
        if (Looper.myLooper() != Looper.getMainLooper()) throw new IllegalStateException("Sampler lifecycle must run on main thread");
        active = false; main.removeCallbacks(sample);
    }
}
