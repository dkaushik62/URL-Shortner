package com.urlshortner.urls;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.databind.JsonNode;
import jakarta.validation.Valid;
import java.net.URI;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeParseException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
public class UrlController {
    public record CreateRequest(@ValidDestination JsonNode url, JsonNode expiresAt) {}
    public record Created(String code, String shortUrl, String url, Instant createdAt,
            @JsonInclude(JsonInclude.Include.ALWAYS) Instant expiresAt) {}
    public record Analytics(String code, String url, Instant createdAt, long clickCount,
            Instant lastAccessedAt, @JsonInclude(JsonInclude.Include.ALWAYS) Instant expiresAt) {}

    private final UrlService service;
    private final String publicBaseUrl;

    public UrlController(UrlService service,
            @Value("${shortener.public-base-url}") String publicBaseUrl) {
        this.service = service;
        URI base = URI.create(publicBaseUrl);
        if (!Destination.valid(publicBaseUrl) || base.getRawQuery() != null || base.getRawFragment() != null) {
            throw new IllegalArgumentException("Invalid public base URL configuration");
        }
        this.publicBaseUrl = publicBaseUrl.replaceAll("/+$", "");
    }

    static Instant parseExpiry(JsonNode value) {
        if (value == null || value.isNull()) return null;
        if (!value.isTextual()) throw new InvalidCreationRequest();
        try {
            OffsetDateTime parsed = OffsetDateTime.parse(value.textValue());
            if (!parsed.getOffset().equals(ZoneOffset.UTC)) throw new InvalidCreationRequest();
            return parsed.toInstant();
        } catch (DateTimeParseException exception) {
            throw new InvalidCreationRequest();
        }
    }

    @PostMapping("/api/urls")
    public ResponseEntity<Created> create(@Valid @RequestBody CreateRequest body) {
        var saved = service.create(body.url().textValue(), parseExpiry(body.expiresAt()));
        String shortUrl = publicBaseUrl + "/r/" + saved.code();
        return ResponseEntity.created(URI.create(shortUrl)).body(new Created(
                saved.code(), shortUrl, saved.url(), saved.createdAt(), saved.expiresAt()));
    }

    @GetMapping("/r/{code}")
    public ResponseEntity<Void> redirect(@PathVariable("code") String code) {
        return ResponseEntity.status(302).location(URI.create(service.redirect(code))).build();
    }

    @GetMapping("/api/urls/{code}/analytics")
    public Analytics analytics(@PathVariable("code") String code) {
        var saved = service.analytics(code);
        return new Analytics(saved.code(), saved.url(), saved.createdAt(), saved.clickCount(),
                saved.lastAccessedAt(), saved.expiresAt());
    }
}
