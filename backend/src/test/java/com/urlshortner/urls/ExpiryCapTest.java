package com.urlshortner.urls;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class ExpiryCapTest {
    @ParameterizedTest
    @ValueSource(longs = {7, 30, 31, 365, Long.MAX_VALUE})
    void configuredLimitCannotExceedSevenDays(long configuredDays) {
        Instant now = Instant.parse("2026-01-01T00:00:00.123456789Z");
        UrlRepository repository = mock(UrlRepository.class);
        CodeGenerator codes = mock(CodeGenerator.class);
        UrlService service = new UrlService(repository, codes,
                Clock.fixed(now, ZoneOffset.UTC), configuredDays);
        String url = "https://example.com";
        Instant maximum = now.plus(Duration.ofDays(7));

        assertThrows(IllegalArgumentException.class, () -> service.create(url, maximum.plusNanos(1)));
        assertThrows(IllegalArgumentException.class,
                () -> service.create(url, now.plus(Duration.ofDays(30))));
        verifyNoInteractions(repository, codes);

        var saved = new UrlRepository.StoredUrl("Ab12Cd34", url, now, 0, null, maximum);
        when(codes.next()).thenReturn(saved.code());
        when(repository.insert(saved.code(), url, maximum)).thenReturn(saved);
        assertSame(saved, service.create(url, maximum));
        verify(repository).insert(saved.code(), url, maximum);
        verify(codes).next();
        verifyNoMoreInteractions(repository, codes);
    }

    @ParameterizedTest
    @ValueSource(longs = {0, -1, Long.MIN_VALUE})
    void rejectsNonpositiveConfiguration(long configuredDays) {
        assertThrows(IllegalArgumentException.class, () -> new UrlService(
                mock(UrlRepository.class), mock(CodeGenerator.class), Clock.systemUTC(), configuredDays));
    }
}
