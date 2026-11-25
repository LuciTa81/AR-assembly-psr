package com.lucita.beastgate;

import java.net.URI;
import okhttp3.HttpUrl;

final class RemoteSupervisorPolicy {
    private RemoteSupervisorPolicy() {}

    static String endpoint(String input, boolean debug) {
        try {
            URI uri = new URI(input.trim());
            String path = uri.getRawPath();
            if (uri.getHost() == null || uri.getRawUserInfo() != null || uri.getRawQuery() != null
                    || uri.getRawFragment() != null || !(path == null || path.isEmpty() || path.equals("/"))
                    || uri.getPort() == 0 || uri.getPort() > 65535) throw new IllegalArgumentException();
            HttpUrl url = HttpUrl.get(uri.toString());
            boolean loopback = url.host().equals("localhost") || url.host().equals("127.0.0.1");
            if (!url.isHttps() && !(debug && loopback && "http".equals(uri.getScheme())))
                throw new IllegalArgumentException();
            return url.toString();
        } catch (Exception e) {
            throw new IllegalArgumentException("HTTPS origin required; debug HTTP is loopback-only");
        }
    }

    static String name(String input) {
        String name = input.trim();
        if (name.isEmpty() || name.length() > 64) throw new IllegalArgumentException("Name must have 1..64 characters");
        return name;
    }

    static boolean mayReconnect(int code, String reason) {
        return code != 4403 && code != 1008 && (code != 4401 || "Reauthenticate".equals(reason));
    }

    static long retryMillis(int attempt, double jitter) {
        long ceiling = Math.min(30000, 1000L << Math.min(5, Math.max(0, attempt)));
        return Math.max(1000, Math.min(30000, (long) (ceiling * (.5 + .5 * jitter))));
    }

    static long sampleMillis(boolean running) { return running ? 250 : 1000; }
}
