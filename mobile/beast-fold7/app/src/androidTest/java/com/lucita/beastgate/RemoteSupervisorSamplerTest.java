package com.lucita.beastgate;

import android.os.Looper;
import androidx.test.platform.app.InstrumentationRegistry;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.Test;
import static org.junit.Assert.*;

public class RemoteSupervisorSamplerTest {
    @Test public void samplesOnlyMainThreadAtIdleRateAndStopsImmediately() throws Exception {
        AtomicInteger samples = new AtomicInteger();
        AtomicBoolean wrongThread = new AtomicBoolean();
        AtomicReference<RemoteSupervisorSampler> sampler = new AtomicReference<>();
        var instrumentation = InstrumentationRegistry.getInstrumentation();
        instrumentation.runOnMainSync(() -> {
            sampler.set(new RemoteSupervisorSampler(() -> {
                if (Looper.myLooper() != Looper.getMainLooper()) wrongThread.set(true);
                samples.incrementAndGet(); return "{\"running\":false}";
            }, () -> true, value -> {}));
            sampler.get().start();
        });
        try {
            Thread.sleep(1250);
            instrumentation.runOnMainSync(() -> sampler.get().close());
            int stoppedAt = samples.get();
            assertEquals(2, stoppedAt); assertFalse(wrongThread.get());
            Thread.sleep(1100); assertEquals(stoppedAt, samples.get());
        } finally { instrumentation.runOnMainSync(() -> sampler.get().close()); }
    }

    @Test public void notReadyNeverReadsArSupplier() throws Exception {
        AtomicInteger samples = new AtomicInteger(); AtomicReference<RemoteSupervisorSampler> sampler = new AtomicReference<>();
        var instrumentation = InstrumentationRegistry.getInstrumentation();
        instrumentation.runOnMainSync(() -> {
            sampler.set(new RemoteSupervisorSampler(() -> { samples.incrementAndGet(); return "{}"; }, () -> false, value -> {}));
            sampler.get().start();
        });
        try { Thread.sleep(600); assertEquals(0, samples.get()); }
        finally { instrumentation.runOnMainSync(() -> sampler.get().close()); }
    }
}
