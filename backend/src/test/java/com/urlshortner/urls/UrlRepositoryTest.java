package com.urlshortner.urls;

import java.sql.ResultSet;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class UrlRepositoryTest {
    @Test
    @SuppressWarnings({"unchecked", "rawtypes"})
    void mapsNullAndExactFractionalExpiryWithoutRounding() throws Exception {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        UrlRepository repository = new UrlRepository(jdbc);
        ArgumentCaptor<RowMapper<UrlRepository.StoredUrl>> mapper = ArgumentCaptor.forClass((Class) RowMapper.class);
        when(jdbc.query(anyString(), any(RowMapper.class), eq("Ab12Cd34"))).thenReturn(List.of());
        repository.find("Ab12Cd34");
        verify(jdbc).query(contains("FROM url_service.urls"), mapper.capture(), eq("Ab12Cd34"));
        ResultSet rs = mock(ResultSet.class);
        Instant expiry = Instant.parse("2026-01-02T00:00:00.123456789Z");
        when(rs.getString("code")).thenReturn("Ab12Cd34");
        when(rs.getString("url")).thenReturn("https://example.com");
        when(rs.getObject("created_at", OffsetDateTime.class)).thenReturn(expiry.atOffset(ZoneOffset.UTC));
        assertNull(mapper.getValue().mapRow(rs, 0).expiresAt());
        when(rs.getObject("expires_at", OffsetDateTime.class)).thenReturn(UrlRepository.micros(expiry));
        when(rs.getInt("expires_at_submicro")).thenReturn(789);
        assertEquals(expiry, mapper.getValue().mapRow(rs, 0).expiresAt());
        assertEquals(Instant.parse("2026-01-02T00:00:00.123456Z"), UrlRepository.micros(expiry).toInstant());
    }

    @Test
    @SuppressWarnings("unchecked")
    void insertSplitsExpiryAndRedirectUsesStrictAtomicPredicate() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        UrlRepository repository = new UrlRepository(jdbc);
        Instant now = Instant.parse("2026-01-02T00:00:00.123456789Z");
        repository.insert("Ab12Cd34", "https://example.com", now);
        verify(jdbc).queryForObject(contains("INSERT INTO url_service.urls"), any(RowMapper.class),
                eq("Ab12Cd34"), eq("https://example.com"), eq(UrlRepository.micros(now)), eq(789));
        when(jdbc.query(anyString(), any(RowMapper.class), any(), any(), any(), any(), any())).thenReturn(List.of());
        assertTrue(repository.recordRedirect("Ab12Cd34", now).isEmpty());
        ArgumentCaptor<String> sql = ArgumentCaptor.forClass(String.class);
        verify(jdbc).query(sql.capture(), any(RowMapper.class), eq(UrlRepository.micros(now)),
                eq("Ab12Cd34"), eq(UrlRepository.micros(now)), eq(UrlRepository.micros(now)), eq(789));
        assertTrue(sql.getValue().contains("UPDATE url_service.urls"));
        assertTrue(sql.getValue().contains("click_count = click_count + 1"));
        assertTrue(sql.getValue().contains("expires_at > ?"));
        assertTrue(sql.getValue().contains("expires_at = ? AND expires_at_submicro > ?"));
        assertTrue(sql.getValue().contains("expires_at IS NULL"));
    }
}
