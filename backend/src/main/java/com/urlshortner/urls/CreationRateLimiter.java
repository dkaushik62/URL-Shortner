package com.urlshortner.urls;

import java.util.Objects;
import java.util.function.LongSupplier;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public final class CreationRateLimiter {
    private static final long SECOND = 1_000_000_000L;
    private static final long WINDOW = 60 * SECOND;

    public static final class LimitExceeded extends RuntimeException {
        private final long retryAfter;

        private LimitExceeded(long retryAfter) {
            super("Creation limit exceeded");
            this.retryAfter = retryAfter;
        }

        public long retryAfter() { return retryAfter; }
    }

    private final int limit;
    private final LongSupplier nanoTime;
    private long started;
    private int admitted;

    @Autowired
    public CreationRateLimiter(@Value("${shortener.creation-limit-per-minute:20}") int limit) {
        this(limit, System::nanoTime);
    }

    CreationRateLimiter(int limit, LongSupplier nanoTime) {
        if (limit < 1) throw new IllegalArgumentException("Invalid creation limit configuration");
        this.limit = limit;
        this.nanoTime = Objects.requireNonNull(nanoTime);
    }

    public synchronized void admit() {
        long now = nanoTime.getAsLong();
        long elapsed = now - started;
        if (admitted == 0 || elapsed >= WINDOW) {
            started = now;
            admitted = 0;
            elapsed = 0;
        }
        if (admitted == limit) {
            long remaining = WINDOW - elapsed;
            throw new LimitExceeded(Math.max(1, (remaining + SECOND - 1) / SECOND));
        }
        admitted++;
    }
}
