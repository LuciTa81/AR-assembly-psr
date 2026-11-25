package com.lucita.beastgate;

final class SessionLimits {
    static final long WORK_MS = 600_000L;
    private SessionLimits() {}

    static long limitMs(boolean standalone, boolean full, boolean assembly) {
        return standalone ? WORK_MS : full ? 300_000L : assembly ? 90_000L : 30_000L;
    }

    static boolean expired(long elapsedMs, boolean standalone, boolean full, boolean assembly) {
        return elapsedMs >= limitMs(standalone, full, assembly);
    }
}
