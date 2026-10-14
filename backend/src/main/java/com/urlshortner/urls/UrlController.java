package com.urlshortner.urls;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.validation.Valid;
import java.net.URI;
import java.time.Instant;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
public class UrlController {
    public record CreateRequest(@ValidDestination JsonNode url) {}
    public record Created(String code, String shortUrl, String url, Instant createdAt) {}
    public record Analytics(String code, String url, Instant createdAt, long clickCount, Instant lastAccessedAt) {}

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

    @PostMapping("/api/urls")
    public ResponseEntity<Created> create(@Valid @RequestBody CreateRequest body) {
        UrlRepository.StoredUrl saved = service.create(body.url().textValue());
        String shortUrl = publicBaseUrl + "/r/" + saved.code();
        return ResponseEntity.created(URI.create(shortUrl))
                .body(new Created(saved.code(), shortUrl, saved.url(), saved.createdAt()));
    }

    @GetMapping("/r/{code}")
    public ResponseEntity<Void> redirect(@PathVariable("code") String code) {
        return ResponseEntity.status(302).location(URI.create(service.redirect(code))).build();
    }

    @GetMapping("/api/urls/{code}/analytics")
    public Analytics analytics(@PathVariable("code") String code) {
        UrlRepository.StoredUrl saved = service.analytics(code);
        return new Analytics(saved.code(), saved.url(), saved.createdAt(), saved.clickCount(), saved.lastAccessedAt());
    }
}
