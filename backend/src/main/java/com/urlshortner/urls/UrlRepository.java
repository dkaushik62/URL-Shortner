package com.urlshortner.urls;

import java.sql.SQLException;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.temporal.ChronoUnit;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.Optional;
import java.util.Set;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

@Repository
public class UrlRepository {
    public record StoredUrl(String code, String url, Instant createdAt, long clickCount,
            Instant lastAccessedAt, Instant expiresAt) {}

    private static final RowMapper<StoredUrl> MAPPER = (rs, row) -> {
        OffsetDateTime accessed = rs.getObject("last_accessed_at", OffsetDateTime.class);
        OffsetDateTime expiry = rs.getObject("expires_at", OffsetDateTime.class);
        return new StoredUrl(rs.getString("code"), rs.getString("url"),
                rs.getObject("created_at", OffsetDateTime.class).toInstant(),
                rs.getLong("click_count"), accessed == null ? null : accessed.toInstant(),
                expiry == null ? null : expiry.toInstant().plusNanos(rs.getInt("expires_at_submicro")));
    };

    private final JdbcTemplate jdbc;

    public UrlRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    static OffsetDateTime micros(Instant instant) {
        return instant.truncatedTo(ChronoUnit.MICROS).atOffset(ZoneOffset.UTC);
    }

    public StoredUrl insert(String code, String url, Instant expiresAt) {
        return jdbc.queryForObject("""
                INSERT INTO url_service.urls (code, url, expires_at, expires_at_submicro)
                VALUES (?, ?, ?, ?)
                RETURNING code, url, created_at, click_count, last_accessed_at,
                          expires_at, expires_at_submicro
                """, MAPPER, code, url, expiresAt == null ? null : micros(expiresAt),
                expiresAt == null ? null : expiresAt.getNano() % 1000);
    }

    public Optional<StoredUrl> find(String code) {
        return jdbc.query("""
                SELECT code, url, created_at, click_count, last_accessed_at,
                       expires_at, expires_at_submicro
                FROM url_service.urls WHERE code = ?
                """, MAPPER, code).stream().findFirst();
    }

    public Optional<String> recordRedirect(String code, Instant now) {
        OffsetDateTime evaluated = micros(now);
        return jdbc.query("""
                UPDATE url_service.urls
                SET click_count = click_count + 1, last_accessed_at = ?
                WHERE code = ? AND (expires_at IS NULL OR expires_at > ?
                    OR (expires_at = ? AND expires_at_submicro > ?))
                RETURNING url
                """, (rs, row) -> rs.getString("url"), evaluated, code,
                evaluated, evaluated, now.getNano() % 1000).stream().findFirst();
    }

    static boolean isCodeConflict(DataAccessException failure) {
        return isCodeConflict(failure, Collections.newSetFromMap(new IdentityHashMap<>()));
    }

    private static boolean isCodeConflict(Throwable failure, Set<Throwable> seen) {
        if (failure == null || !seen.add(failure)) return false;
        if (failure instanceof SQLException sql) {
            if ("23505".equals(sql.getSQLState()) && namedCodeConstraint(sql)) return true;
            if (isCodeConflict(sql.getNextException(), seen)) return true;
        }
        return isCodeConflict(failure.getCause(), seen);
    }

    private static boolean namedCodeConstraint(SQLException failure) {
        if (!failure.getClass().getName().equals("org.postgresql.util.PSQLException")) return false;
        try {
            Object detail = failure.getClass().getMethod("getServerErrorMessage").invoke(failure);
            if (detail == null) return false;
            return "pk_urls_code".equals(detail.getClass().getMethod("getConstraint").invoke(detail))
                    && "url_service".equals(detail.getClass().getMethod("getSchema").invoke(detail))
                    && "urls".equals(detail.getClass().getMethod("getTable").invoke(detail));
        } catch (ReflectiveOperationException | SecurityException exception) {
            return false;
        }
    }
}
