package com.urlshortner.urls;

import java.sql.SQLException;
import java.time.*;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.dao.DuplicateKeyException;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class UrlServiceTest {
    private static final Instant T = Instant.parse("2026-01-01T00:00:00.123456789Z");
    private static final String URL = "https://example.com/a";
    private final UrlRepository repository = mock(UrlRepository.class);
    private final CodeGenerator codes = mock(CodeGenerator.class);
    private final Clock clock = mock(Clock.class);
    private final UrlService service = new UrlService(repository, codes, clock, 30);

    private void setup() {
        when(clock.instant()).thenReturn(T);
        when(codes.next()).thenReturn("Ab12Cd34");
    }

    private UrlRepository.StoredUrl saved(Instant expiry) {
        return new UrlRepository.StoredUrl("Ab12Cd34", URL, T, 0, null, expiry);
    }

    private DuplicateKeyException conflict(String constraint, String state) throws Exception {
        Class<?> detailType = Class.forName("org.postgresql.util.ServerErrorMessage");
        Object detail = detailType.getConstructor(String.class).newInstance(
                "SERROR\0C" + state + "\0Mduplicate\0surl_service\0turls\0n" + constraint + "\0\0");
        SQLException sql = (SQLException) Class.forName("org.postgresql.util.PSQLException")
                .getConstructor(detailType).newInstance(detail);
        return new DuplicateKeyException("collision", sql);
    }

    @Test
    void acceptsNullOneNanosecondAndInclusiveMaximum() {
        setup();
        for (Instant expiry : new Instant[] {null, T.plusNanos(1), T.plus(Duration.ofDays(7))}) {
            var saved = saved(expiry);
            when(repository.insert("Ab12Cd34", URL, expiry)).thenReturn(saved);
            assertSame(saved, service.create(URL, expiry));
        }
        verify(clock, times(3)).instant();
    }

    @Test
    void rejectsInvalidExpiryBeforeAllocation() {
        setup();
        for (Instant expiry : new Instant[] {T.minusNanos(1), T, T.plus(Duration.ofDays(7)).plusNanos(1)}) {
            assertThrows(IllegalArgumentException.class, () -> service.create(URL, expiry));
        }
        assertThrows(IllegalArgumentException.class, () -> service.create("ftp://example.com", null));
        verifyNoInteractions(repository);
        verify(codes, never()).next();
    }

    @Test
    void configuredMaximumIsUsed() {
        setup();
        var configured = new UrlService(repository, codes, clock, 2);
        Instant maximum = T.plus(Duration.ofDays(2));
        assertThrows(IllegalArgumentException.class, () -> configured.create(URL, maximum.plusNanos(1)));
        verifyNoInteractions(repository);
        verify(codes, never()).next();
        var saved = saved(maximum);
        when(repository.insert("Ab12Cd34", URL, maximum)).thenReturn(saved);
        assertSame(saved, configured.create(URL, maximum));
    }

    @Test
    void retriesWithoutReadingClockAgainAndCanSucceedOnFifthAttempt() throws Exception {
        setup();
        when(clock.instant()).thenReturn(T, T.plus(Duration.ofDays(40)));
        Instant expiry = T.plusNanos(1);
        var saved = saved(expiry);
        var collision = conflict("pk_urls_code", "23505");
        when(repository.insert("Ab12Cd34", URL, expiry)).thenThrow(collision).thenThrow(collision)
                .thenThrow(collision).thenThrow(collision).thenReturn(saved);
        assertSame(saved, service.create(URL, expiry));
        verify(clock).instant();
        verify(codes, times(5)).next();
    }

    @Test
    void stopsAfterFiveCollisions() throws Exception {
        setup();
        when(repository.insert("Ab12Cd34", URL, null)).thenThrow(conflict("pk_urls_code", "23505"));
        assertThrows(UrlService.AllocationExhausted.class, () -> service.create(URL, null));
        verify(repository, times(5)).insert("Ab12Cd34", URL, null);
    }

    @Test
    void unrelatedFailuresAreNotRetried() throws Exception {
        setup();
        for (var failure : new org.springframework.dao.DataAccessException[] {
                conflict("other", "23505"), conflict("pk_urls_code", "23503"),
                new DuplicateKeyException("pk_urls_code", new SQLException("pk_urls_code", "23505")),
                new DataAccessResourceFailureException("unavailable")}) {
            reset(repository);
            when(repository.insert("Ab12Cd34", URL, null)).thenThrow(failure);
            assertSame(failure, assertThrows(failure.getClass(), () -> service.create(URL, null)));
            verify(repository).insert("Ab12Cd34", URL, null);
        }
    }

    @Test
    void successfulRedirectUsesOneAtomicOperation() {
        setup();
        when(repository.recordRedirect("Ab12Cd34", T)).thenReturn(Optional.of(URL));
        assertEquals(URL, service.redirect("Ab12Cd34"));
        verify(repository).recordRedirect("Ab12Cd34", T);
        verify(repository, never()).find(anyString());
        verify(clock).instant();
    }

    @Test
    void equalityAndPastExpiryAreGoneButAnalyticsRemainsAvailable() {
        setup();
        when(repository.recordRedirect("Ab12Cd34", T)).thenReturn(Optional.empty());
        for (Instant expiry : new Instant[] {T, T.minusNanos(1)}) {
            var saved = saved(expiry);
            when(repository.find("Ab12Cd34")).thenReturn(Optional.of(saved));
            assertThrows(UrlService.ExpiredCode.class, () -> service.redirect("Ab12Cd34"));
            assertSame(saved, service.analytics("Ab12Cd34"));
        }
        verify(repository, times(2)).recordRedirect("Ab12Cd34", T);
        verify(repository, never()).insert(anyString(), anyString(), any());
    }

    @Test
    void advancingClockPassesEqualityToAtomicAccounting() {
        setup();
        Instant expiry = T.plusNanos(1);
        when(clock.instant()).thenReturn(T, expiry, expiry.plusNanos(1));
        when(repository.recordRedirect("Ab12Cd34", T)).thenReturn(Optional.of(URL));
        when(repository.recordRedirect("Ab12Cd34", expiry)).thenReturn(Optional.empty());
        when(repository.recordRedirect("Ab12Cd34", expiry.plusNanos(1))).thenReturn(Optional.empty());
        when(repository.find("Ab12Cd34")).thenReturn(Optional.of(saved(expiry)));
        assertEquals(URL, service.redirect("Ab12Cd34"));
        assertThrows(UrlService.ExpiredCode.class, () -> service.redirect("Ab12Cd34"));
        assertThrows(UrlService.ExpiredCode.class, () -> service.redirect("Ab12Cd34"));
        verify(clock, times(3)).instant();
        verify(repository).recordRedirect("Ab12Cd34", T);
        verify(repository).recordRedirect("Ab12Cd34", expiry);
        verify(repository).recordRedirect("Ab12Cd34", expiry.plusNanos(1));
    }

    @Test
    void unknownCodesAreAbsent() {
        setup();
        when(repository.recordRedirect("missing", T)).thenReturn(Optional.empty());
        when(repository.find("missing")).thenReturn(Optional.empty());
        assertThrows(UrlService.UnknownCode.class, () -> service.redirect("missing"));
        assertThrows(UrlService.UnknownCode.class, () -> service.analytics("missing"));
        verify(repository).recordRedirect("missing", T);
    }

    @Test
    void analyticsDoesNotReadClockOrRecordRedirect() {
        var stored = saved(T.minusNanos(1));
        when(repository.find("Ab12Cd34")).thenReturn(Optional.of(stored));
        assertSame(stored, service.analytics("Ab12Cd34"));
        verify(repository).find("Ab12Cd34");
        verifyNoMoreInteractions(repository);
        verifyNoInteractions(clock, codes);
    }

    @Test
    void repositoryFailureCannotProduceSuccessfulRedirect() {
        when(clock.instant()).thenReturn(T);
        var failure = new DataAccessResourceFailureException("unavailable");
        when(repository.recordRedirect("Ab12Cd34", T)).thenThrow(failure);
        assertSame(failure, assertThrows(DataAccessResourceFailureException.class,
                () -> service.redirect("Ab12Cd34")));
        verify(repository).recordRedirect("Ab12Cd34", T);
        verifyNoMoreInteractions(repository);
        verify(clock).instant();
    }

    @Test
    void generatedCodesHaveRequiredAlphabetAndLength() {
        var generator = new CodeGenerator();
        for (int i = 0; i < 100; i++) assertTrue(generator.next().matches("[0-9A-Za-z]{8}"));
    }
}
