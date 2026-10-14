package com.urlshortner.urls;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.DataAccessException;
import org.springframework.stereotype.Service;

@Service
public class UrlService {
    public static final class UnknownCode extends RuntimeException {}
    public static final class ExpiredCode extends RuntimeException {}
    public static final class AllocationExhausted extends RuntimeException {}

    private final UrlRepository repository;
    private final CodeGenerator codes;
    private final Clock clock;
    private final Duration maximumExpiry;

    public UrlService(UrlRepository repository, CodeGenerator codes, Clock clock,
            @Value("${shortener.max-expiry-days:7}") long maximumDays) {
        if (maximumDays <= 0) throw new IllegalArgumentException("Invalid maximum expiry configuration");
        this.repository = repository;
        this.codes = codes;
        this.clock = clock;
        this.maximumExpiry = Duration.ofDays(Math.min(maximumDays, 7L));
    }

    // No surrounding transaction: a uniqueness failure must not abort later attempts.
    public UrlRepository.StoredUrl create(String url, Instant expiresAt) {
        if (!Destination.valid(url)) throw new InvalidCreationRequest();
        Instant now = clock.instant();
        if (expiresAt != null && (!expiresAt.isAfter(now)
                || expiresAt.isAfter(now.plus(maximumExpiry)))) {
            throw new InvalidCreationRequest();
        }
        for (int attempt = 0; attempt < 5; attempt++) {
            try {
                return repository.insert(codes.next(), url, expiresAt);
            } catch (DataAccessException exception) {
                if (!UrlRepository.isCodeConflict(exception)) throw exception;
                RequestEvents.collision(attempt + 1);
            }
        }
        throw new AllocationExhausted();
    }

    public String redirect(String code) {
        Instant now = clock.instant();
        var destination = repository.recordRedirect(code, now);
        if (destination.isPresent()) return destination.get();
        var stored = repository.find(code).orElseThrow(UnknownCode::new);
        if (stored.expiresAt() != null && !stored.expiresAt().isAfter(now)) throw new ExpiredCode();
        throw new IllegalStateException("Eligible redirect was not updated");
    }

    public UrlRepository.StoredUrl analytics(String code) {
        return repository.find(code).orElseThrow(UnknownCode::new);
    }
}
