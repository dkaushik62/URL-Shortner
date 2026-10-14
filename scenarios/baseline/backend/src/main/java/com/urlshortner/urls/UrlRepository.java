package com.urlshortner.urls;

import java.lang.reflect.InvocationTargetException;
import java.sql.SQLException;
import java.time.Instant;
import java.time.OffsetDateTime;
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
    public record StoredUrl(String code, String url, Instant createdAt, long clickCount, Instant lastAccessedAt) {}

    private static final RowMapper<StoredUrl> MAPPER = (rs, row) -> {
        OffsetDateTime lastAccessed = rs.getObject("last_accessed_at", OffsetDateTime.class);
        return new StoredUrl(rs.getString("code"), rs.getString("url"),
                rs.getObject("created_at", OffsetDateTime.class).toInstant(),
                rs.getLong("click_count"), lastAccessed == null ? null : lastAccessed.toInstant());
    };

    private final JdbcTemplate jdbc;

    public UrlRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public StoredUrl insert(String code, String url) {
        return jdbc.queryForObject("""
                INSERT INTO url_service.urls (code, url) VALUES (?, ?)
                RETURNING code, url, created_at, click_count, last_accessed_at
                """, MAPPER, code, url);
    }

    public Optional<StoredUrl> find(String code) {
        return jdbc.query("""
                SELECT code, url, created_at, click_count, last_accessed_at
                FROM url_service.urls WHERE code = ?
                """, MAPPER, code).stream().findFirst();
    }

    public Optional<String> recordRedirect(String code) {
        return jdbc.query("""
                UPDATE url_service.urls
                SET click_count = click_count + 1, last_accessed_at = clock_timestamp()
                WHERE code = ? RETURNING url
                """, (rs, row) -> rs.getString("url"), code).stream().findFirst();
    }

    static boolean isCodeConflict(DataAccessException failure) {
        Set<Throwable> seen = Collections.newSetFromMap(new IdentityHashMap<>());
        return isCodeConflict(failure, seen);
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
        // The PostgreSQL driver is runtime-only. Read its structured diagnostics,
        // never localized message text, and fail closed for unknown drivers.
        if (!failure.getClass().getName().equals("org.postgresql.util.PSQLException")) return false;
        try {
            Object detail = failure.getClass().getMethod("getServerErrorMessage").invoke(failure);
            if (detail == null) return false;
            Object constraint = detail.getClass().getMethod("getConstraint").invoke(detail);
            Object schema = detail.getClass().getMethod("getSchema").invoke(detail);
            Object table = detail.getClass().getMethod("getTable").invoke(detail);
            return "pk_urls_code".equals(constraint)
                    && "url_service".equals(schema) && "urls".equals(table);
        } catch (ReflectiveOperationException | SecurityException exception) {
            return false;
        }
    }
}
