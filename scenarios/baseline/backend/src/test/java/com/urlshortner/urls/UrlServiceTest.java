package com.urlshortner.urls;

import java.sql.SQLException;
import java.time.Instant;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.dao.DuplicateKeyException;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class UrlServiceTest {
    private final UrlRepository repository = mock(UrlRepository.class);
    private final CodeGenerator codes = mock(CodeGenerator.class);
    private final UrlService service = new UrlService(repository, codes);
    private final UrlRepository.StoredUrl saved = new UrlRepository.StoredUrl(
            "Ab12Cd34", "https://example.com/a", Instant.parse("2026-01-01T00:00:00Z"), 0, null);

    @BeforeEach
    void setUp() {
        when(codes.next()).thenReturn(saved.code());
    }

    private DuplicateKeyException conflict(String constraint, String state) throws Exception {
        // Construct actual runtime-driver metadata without a compile-time driver dependency.
        Class<?> detailType = Class.forName("org.postgresql.util.ServerErrorMessage");
        String fields = "SERROR\0C" + state + "\0Mduplicate\0surl_service\0turls\0n" + constraint + "\0\0";
        Object detail = detailType.getConstructor(String.class).newInstance(fields);
        SQLException sql = (SQLException) Class.forName("org.postgresql.util.PSQLException")
                .getConstructor(detailType).newInstance(detail);
        return new DuplicateKeyException("collision", sql);
    }

    @Test
    void preservesStoredCreationValues() {
        when(repository.insert(saved.code(), saved.url())).thenReturn(saved);
        assertSame(saved, service.create(saved.url()));
        verify(repository).insert(saved.code(), saved.url());
    }

    @Test
    void recoversFromOneCollision() throws Exception {
        when(codes.next()).thenReturn("00000000", saved.code());
        when(repository.insert("00000000", saved.url())).thenThrow(conflict("pk_urls_code", "23505"));
        when(repository.insert(saved.code(), saved.url())).thenReturn(saved);
        assertSame(saved, service.create(saved.url()));
        verify(codes, times(2)).next();
    }

    @Test
    void succeedsOnFifthAttempt() throws Exception {
        DuplicateKeyException collision = conflict("pk_urls_code", "23505");
        when(repository.insert(saved.code(), saved.url()))
                .thenThrow(collision).thenThrow(collision).thenThrow(collision).thenThrow(collision).thenReturn(saved);
        assertSame(saved, service.create(saved.url()));
        verify(repository, times(5)).insert(saved.code(), saved.url());
    }

    @Test
    void stopsAfterFiveCollisions() throws Exception {
        when(repository.insert(saved.code(), saved.url())).thenThrow(conflict("pk_urls_code", "23505"));
        assertThrows(UrlService.AllocationExhausted.class, () -> service.create(saved.url()));
        verify(repository, times(5)).insert(saved.code(), saved.url());
        verify(codes, times(5)).next();
    }

    @Test
    void doesNotRetryOtherConstraintsOrStates() throws Exception {
        for (DuplicateKeyException failure : new DuplicateKeyException[] {
                conflict("other_constraint", "23505"), conflict("pk_urls_code", "23503"),
                new DuplicateKeyException("pk_urls_code", new SQLException("pk_urls_code", "23505"))
        }) {
            reset(repository);
            when(repository.insert(saved.code(), saved.url())).thenThrow(failure);
            assertSame(failure, assertThrows(DuplicateKeyException.class, () -> service.create(saved.url())));
            verify(repository).insert(saved.code(), saved.url());
        }
    }

    @Test
    void propagatesDatabaseFailuresImmediately() {
        var failure = new DataAccessResourceFailureException("unavailable");
        when(repository.insert(saved.code(), saved.url())).thenThrow(failure);
        assertSame(failure, assertThrows(DataAccessResourceFailureException.class, () -> service.create(saved.url())));
        verify(repository).insert(saved.code(), saved.url());
    }

    @Test
    void invalidDestinationDoesNotReachPersistence() {
        assertThrows(IllegalArgumentException.class, () -> service.create("ftp://example.com"));
        verifyNoInteractions(repository, codes);
    }

    @Test
    void redirectAccountsExactlyOnceAndAnalyticsOnlyReads() {
        when(repository.recordRedirect(saved.code())).thenReturn(Optional.of(saved.url()));
        when(repository.find(saved.code())).thenReturn(Optional.of(saved));
        assertEquals(saved.url(), service.redirect(saved.code()));
        verify(repository).recordRedirect(saved.code());
        clearInvocations(repository);
        assertSame(saved, service.analytics(saved.code()));
        verify(repository).find(saved.code());
        verify(repository, never()).recordRedirect(anyString());
    }

    @Test
    void unknownCodesAreExplicitlyAbsent() {
        when(repository.recordRedirect("missing")).thenReturn(Optional.empty());
        when(repository.find("missing")).thenReturn(Optional.empty());
        assertThrows(UrlService.UnknownCode.class, () -> service.redirect("missing"));
        assertThrows(UrlService.UnknownCode.class, () -> service.analytics("missing"));
    }

    @Test
    void generatedCodesHaveRequiredAlphabetAndLength() {
        CodeGenerator generator = new CodeGenerator();
        for (int i = 0; i < 100; i++) assertTrue(generator.next().matches("[0-9A-Za-z]{8}"));
    }
}
