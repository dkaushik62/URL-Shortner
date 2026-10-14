package com.urlshortner.urls;

import com.fasterxml.jackson.databind.SerializationFeature;
import java.time.Instant;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.http.MediaType;
import org.springframework.http.converter.json.Jackson2ObjectMapperBuilder;
import org.springframework.http.converter.json.MappingJackson2HttpMessageConverter;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.validation.beanvalidation.LocalValidatorFactoryBean;
import static org.hamcrest.Matchers.nullValue;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class UrlControllerTest {
    private final UrlService service = mock(UrlService.class);
    private final LocalValidatorFactoryBean validator = new LocalValidatorFactoryBean();
    private final UrlRepository.StoredUrl saved = new UrlRepository.StoredUrl(
            "Ab12Cd34", "https://example.com/a?b=1#part", Instant.parse("2026-01-01T00:00:00Z"), 0, null);
    private MockMvc mvc;

    @BeforeEach
    void setUp() {
        validator.afterPropertiesSet();
        mvc = mvcFor("https://public.example:8443/links/");
    }

    private MockMvc mvcFor(String base) {
        var mapper = Jackson2ObjectMapperBuilder.json()
                .featuresToDisable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS).build();
        return MockMvcBuilders.standaloneSetup(new UrlController(service, base))
                .setControllerAdvice(new UrlErrors()).setValidator(validator)
                .setMessageConverters(new MappingJackson2HttpMessageConverter(mapper)).build();
    }

    @AfterEach
    void closeValidator() {
        validator.close();
    }

    @Test
    void creationUsesConfiguredBaseDespiteConflictingClientOrigin() throws Exception {
        when(service.create(saved.url())).thenReturn(saved);
        mvc.perform(post("/app/api/urls").contextPath("/app")
                        .with(request -> {
                            request.setScheme("http");
                            request.setServerName("untrusted.example");
                            request.setServerPort(9999);
                            return request;
                        })
                        .header("Host", "attacker.example:9999")
                        .header("Forwarded", "proto=http;host=forwarded.example")
                        .header("X-Forwarded-Host", "forwarded.example")
                        .header("X-Forwarded-Proto", "http")
                        .header("X-Forwarded-Port", "80")
                        .contentType(MediaType.APPLICATION_JSON).content(body()))
                .andExpect(status().isCreated())
                .andExpect(header().string("Location", "https://public.example:8443/links/r/Ab12Cd34"))
                .andExpect(jsonPath("$.code").value(saved.code()))
                .andExpect(jsonPath("$.shortUrl").value("https://public.example:8443/links/r/Ab12Cd34"))
                .andExpect(jsonPath("$.url").value(saved.url()))
                .andExpect(jsonPath("$.createdAt").value("2026-01-01T00:00:00Z"));
        verify(service).create(saved.url());
        verifyNoMoreInteractions(service);
    }

    @ParameterizedTest
    @ValueSource(strings = {"http://127.0.0.1:8000", "http://127.0.0.1:8000/"})
    void rootBaseProducesOnePathSeparator(String base) throws Exception {
        when(service.create(saved.url())).thenReturn(saved);
        mvcFor(base).perform(post("/api/urls").contentType(MediaType.APPLICATION_JSON).content(body()))
                .andExpect(status().isCreated())
                .andExpect(header().string("Location", "http://127.0.0.1:8000/r/Ab12Cd34"))
                .andExpect(jsonPath("$.shortUrl").value("http://127.0.0.1:8000/r/Ab12Cd34"));
    }

    @ParameterizedTest
    @ValueSource(strings = {"/relative", "ftp://example.com", "https://user@example.com",
            "https://example.com/?query=1", "https://example.com/#fragment"})
    void rejectsInvalidPublicBaseConfiguration(String base) {
        assertThrows(IllegalArgumentException.class, () -> new UrlController(service, base));
    }

    private String body() {
        return "{\"url\":\"" + saved.url() + "\"}";
    }

    @ParameterizedTest
    @ValueSource(strings = {
            "", "{", "null", "[]", "{}", "{\"url\":null}", "{\"url\":42}",
            "{\"url\":true}", "{\"url\":{}}", "{\"url\":[]}", "{\"url\":\"\"}",
            "{\"url\":\"ftp://example.com\"}", "{\"url\":\"https://user@example.com\"}",
            "{\"url\":\"https://example.com/\\r\\n\"}"
    })
    void rejectsInvalidBodiesWithoutCallingService(String body) throws Exception {
        mvc.perform(post("/api/urls").contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isBadRequest());
        verifyNoInteractions(service);
    }

    @Test
    void redirectsOnceWithExactDestination() throws Exception {
        when(service.redirect(saved.code())).thenReturn(saved.url());
        mvc.perform(get("/r/{code}", saved.code()))
                .andExpect(status().isFound()).andExpect(header().string("Location", saved.url()));
        verify(service).redirect(saved.code());
        verifyNoMoreInteractions(service);
    }

    @Test
    void initialAnalyticsHasZeroClicksAndNullAccessTime() throws Exception {
        when(service.analytics(saved.code())).thenReturn(saved);
        mvc.perform(get("/api/urls/{code}/analytics", saved.code()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(saved.code()))
                .andExpect(jsonPath("$.url").value(saved.url()))
                .andExpect(jsonPath("$.createdAt").value("2026-01-01T00:00:00Z"))
                .andExpect(jsonPath("$.clickCount").value(0))
                .andExpect(jsonPath("$.lastAccessedAt").value(nullValue()));
        verify(service).analytics(saved.code());
        verifyNoMoreInteractions(service);
    }

    @Test
    void analyticsIncludesRecordedAccessTime() throws Exception {
        when(service.analytics(saved.code())).thenReturn(new UrlRepository.StoredUrl(
                saved.code(), saved.url(), saved.createdAt(), 12, Instant.parse("2026-01-02T00:00:00Z")));
        mvc.perform(get("/api/urls/{code}/analytics", saved.code()))
                .andExpect(status().isOk()).andExpect(jsonPath("$.clickCount").value(12))
                .andExpect(jsonPath("$.lastAccessedAt").value("2026-01-02T00:00:00Z"));
    }

    @Test
    void mapsUnknownCodesTo404() throws Exception {
        when(service.redirect("missing")).thenThrow(new UrlService.UnknownCode());
        when(service.analytics("missing")).thenThrow(new UrlService.UnknownCode());
        mvc.perform(get("/r/missing")).andExpect(status().isNotFound());
        mvc.perform(get("/api/urls/missing/analytics")).andExpect(status().isNotFound());
    }

    @Test
    void mapsExhaustionTo503AndHidesInternalDetails() throws Exception {
        when(service.create(saved.url())).thenThrow(new UrlService.AllocationExhausted());
        mvc.perform(post("/api/urls").contentType(MediaType.APPLICATION_JSON).content(body()))
                .andExpect(status().isServiceUnavailable());
        when(service.analytics("broken")).thenThrow(new IllegalStateException("private SQL diagnostics"));
        mvc.perform(get("/api/urls/broken/analytics"))
                .andExpect(status().isInternalServerError())
                .andExpect(content().json("{\"error\":\"Internal server error\"}"));
    }
}
