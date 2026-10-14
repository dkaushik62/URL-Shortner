package com.urlshortner.urls;

import java.util.ArrayList;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class CreationRateLimiterTest {
    @Test
    void roundsRetryAndResetsAtExactBoundaryWithoutExtendingRejections() {
        AtomicLong time = new AtomicLong(-100);
        CreationRateLimiter limiter = new CreationRateLimiter(1, time::get);
        limiter.admit();
        assertEquals(60, rejected(limiter));
        time.incrementAndGet();
        assertEquals(60, rejected(limiter));
        time.set(-100 + 59_000_000_000L);
        assertEquals(1, rejected(limiter));
        time.set(-100 + 60_000_000_000L - 1);
        assertEquals(1, rejected(limiter));
        time.incrementAndGet();
        limiter.admit();
        assertEquals(60, rejected(limiter));
        time.addAndGet(600_000_000_000L);
        limiter.admit();
        assertEquals(60, rejected(limiter));
    }

    @Test
    void supportsNanoTimeWraparound() {
        AtomicLong time = new AtomicLong(Long.MAX_VALUE - 10);
        CreationRateLimiter limiter = new CreationRateLimiter(1, time::get);
        limiter.admit();
        time.addAndGet(60_000_000_000L);
        limiter.admit();
        assertEquals(60, rejected(limiter));
    }

    @Test
    void validatesConfigurationAndHonorsPositiveOverrides() {
        for (int invalid : new int[] {0, -1, Integer.MIN_VALUE}) {
            assertThrows(IllegalArgumentException.class, () -> new CreationRateLimiter(invalid));
        }
        for (int limit : new int[] {1, 3, 20}) {
            CreationRateLimiter limiter = new CreationRateLimiter(limit, () -> 0L);
            for (int i = 0; i < limit; i++) limiter.admit();
            assertEquals(60, rejected(limiter));
        }
    }

    @Test
    void admitsExactlyTwentyConcurrentAttemptsInEachWindow() throws Exception {
        AtomicLong time = new AtomicLong();
        CreationRateLimiter limiter = new CreationRateLimiter(20, time::get);
        var workers = Executors.newFixedThreadPool(16);
        try {
            for (int window = 0; window < 2; window++) {
                CountDownLatch start = new CountDownLatch(1);
                var results = new ArrayList<Future<Boolean>>();
                for (int i = 0; i < 100; i++) {
                    results.add(workers.submit(() -> {
                        if (!start.await(5, TimeUnit.SECONDS)) throw new AssertionError("Start timeout");
                        try {
                            limiter.admit();
                            return true;
                        } catch (CreationRateLimiter.LimitExceeded exception) {
                            assertEquals(60, exception.retryAfter());
                            return false;
                        }
                    }));
                }
                start.countDown();
                int admitted = 0;
                for (Future<Boolean> result : results) {
                    if (result.get(10, TimeUnit.SECONDS)) admitted++;
                }
                assertEquals(20, admitted);
                time.addAndGet(60_000_000_000L);
            }
        } finally {
            workers.shutdownNow();
            assertTrue(workers.awaitTermination(5, TimeUnit.SECONDS));
        }
    }

    private long rejected(CreationRateLimiter limiter) {
        return assertThrows(CreationRateLimiter.LimitExceeded.class, limiter::admit).retryAfter();
    }
}
