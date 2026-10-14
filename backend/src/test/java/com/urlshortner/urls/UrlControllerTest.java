package com.urlshortner.urls;

import com.fasterxml.jackson.databind.SerializationFeature;
import com.urlshortner.InjectedRedirectFaultFilter;
import java.time.Instant;
import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.http.MediaType;
import org.springframework.http.converter.json.Jackson2ObjectMapperBuilder;
import org.springframework.http.converter.json.MappingJackson2HttpMessageConverter;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.validation.beanvalidation.LocalValidatorFactoryBean;
import static org.hamcrest.Matchers.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class UrlControllerTest {
    private final UrlService service = mock(UrlService.class);
    private final LocalValidatorFactoryBean validator = new LocalValidatorFactoryBean();
    private final Instant created = Instant.parse("2026-01-01T00:00:00Z");
    private MockMvc mvc;

    @BeforeEach
    void setup() {
        validator.afterPropertiesSet();
        mvc = mvcFor("https://public.example:8443/links/");
    }

    private MockMvc mvcFor(String base) {
        var mapper = Jackson2ObjectMapperBuilder.json()
                .featuresToDisable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS).build();
        return MockMvcBuilders.standaloneSetup(new UrlController(service, base))
                .setControllerAdvice(new UrlErrors()).setValidator(validator)
                .addFilters(new RequestCorrelationFilter(), new InjectedRedirectFaultFilter())
                .setMessageConverters(new MappingJackson2HttpMessageConverter(mapper)).build();
    }

    @AfterEach
    void close() { validator.close(); }

    private UrlRepository.StoredUrl saved(Instant expiry) {
        return new UrlRepository.StoredUrl("Ab12Cd34", "https://example.com/a?b=1#part", created, 0, null, expiry);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", ",\"expiresAt\":null"})
    void omittedAndNullExpiryPreserveConfiguredPublicUrl(String suffix) throws Exception {
        var saved = saved(null);
        when(service.create(saved.url(), null)).thenReturn(saved);
        mvc.perform(post("/app/api/urls").contextPath("/app")
                        .header("Host", "attacker.example")
                        .header("Forwarded", "proto=http;host=attacker.example")
                        .header("X-Forwarded-Host", "attacker.example")
                        .header("X-Forwarded-Proto", "http")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"url\":\"" + saved.url() + "\"" + suffix + "}"))
                .andExpect(status().isCreated())
                .andExpect(header().string("Location", "https://public.example:8443/links/r/Ab12Cd34"))
                .andExpect(jsonPath("$.shortUrl").value("https://public.example:8443/links/r/Ab12Cd34"))
                .andExpect(jsonPath("$.code").value(saved.code()))
                .andExpect(jsonPath("$.url").value(saved.url()))
                .andExpect(jsonPath("$.createdAt").value(created.toString()))
                .andExpect(jsonPath("$", hasKey("expiresAt")))
                .andExpect(jsonPath("$.expiresAt").value(nullValue()));
        verify(service).create(saved.url(), null);
        verifyNoMoreInteractions(service);
    }

    @ParameterizedTest
    @ValueSource(strings = {"2026-01-02T00:00:00.123456789Z", "2026-01-02T00:00:00.123456789+00:00"})
    void exposesExactExpiryOnCreationAndAnalytics(String text) throws Exception {
        Instant expiry = Instant.parse("2026-01-02T00:00:00.123456789Z");
        var saved = saved(expiry);
        when(service.create(saved.url(), expiry)).thenReturn(saved);
        when(service.analytics(saved.code())).thenReturn(saved);
        mvc.perform(post("/api/urls").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"url\":\"" + saved.url() + "\",\"expiresAt\":\"" + text + "\"}"))
                .andExpect(status().isCreated()).andExpect(jsonPath("$.expiresAt").value(expiry.toString()));
        mvc.perform(get("/api/urls/Ab12Cd34/analytics"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.expiresAt").value(expiry.toString()))
                .andExpect(jsonPath("$.clickCount").value(0))
                .andExpect(jsonPath("$.lastAccessedAt").value(nullValue()));
    }

    @ParameterizedTest
    @ValueSource(strings = {"42", "true", "[]", "{}", "\"\"", "\"bad\"",
            "\"2026-01-02T00:00:00\"", "\"2026-01-02T01:00:00+01:00\""})
    void rejectsExpiryTypesAndNonUtcValues(String expiry) throws Exception {
        mvc.perform(post("/api/urls").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"url\":\"https://example.com\",\"expiresAt\":" + expiry + "}"))
                .andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value("INVALID_INPUT"));
        verifyNoInteractions(service);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", "{", "null", "[]", "{}", "{\"url\":null}",
            "{\"url\":42}", "{\"url\":true}", "{\"url\":{}}", "{\"url\":[]}",
            "{\"url\":\"\"}", "{\"url\":\"ftp://example.com\"}",
            "{\"url\":\"https://user@example.com\"}", "{\"url\":\"https://example.com/\\r\\n\"}"})
    void invalidBodiesDoNotCallService(String body) throws Exception {
        mvc.perform(post("/api/urls").contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value("INVALID_INPUT"));
        verifyNoInteractions(service);
    }

    @Test
    void redirectsAndMapsErrorsWithoutLeakingDetails() throws Exception {
        when(service.redirect("valid")).thenReturn("https://example.com/a?b=1#part");
        when(service.redirect("expired")).thenThrow(new UrlService.ExpiredCode());
        when(service.redirect("missing")).thenThrow(new UrlService.UnknownCode());
        when(service.analytics("missing")).thenThrow(new UrlService.UnknownCode());
        when(service.analytics("broken")).thenThrow(new IllegalStateException("private SQL"));
        mvc.perform(get("/r/valid")).andExpect(status().isFound())
                .andExpect(header().string("Location", "https://example.com/a?b=1#part"));
        mvc.perform(get("/r/expired")).andExpect(status().isGone()).andExpect(header().doesNotExist("Location"))
                .andExpect(jsonPath("$.code").value("LINK_EXPIRED"));
        mvc.perform(get("/r/missing")).andExpect(status().isNotFound()).andExpect(header().doesNotExist("Location"))
                .andExpect(jsonPath("$.code").value("LINK_NOT_FOUND"));
        mvc.perform(get("/api/urls/missing/analytics")).andExpect(status().isNotFound());
        mvc.perform(get("/api/urls/broken/analytics")).andExpect(status().isInternalServerError())
                .andExpect(jsonPath("$.code").value("INTERNAL_ERROR"))
                .andExpect(jsonPath("$.message").value("Internal server error"));
        verify(service).redirect("valid");
    }

    @Test
    void nonExpiringAnalyticsIncludesExplicitNullAndRecordedAccess() throws Exception {
        when(service.analytics("Ab12Cd34")).thenReturn(new UrlRepository.StoredUrl(
                "Ab12Cd34", "https://example.com", created, 12, created.plusSeconds(1), null));
        mvc.perform(get("/api/urls/Ab12Cd34/analytics")).andExpect(status().isOk())
                .andExpect(jsonPath("$.clickCount").value(12))
                .andExpect(jsonPath("$.lastAccessedAt").value(created.plusSeconds(1).toString()))
                .andExpect(jsonPath("$", hasKey("expiresAt")))
                .andExpect(jsonPath("$.expiresAt").value(nullValue()));
        verify(service).analytics("Ab12Cd34");
        verifyNoMoreInteractions(service);
    }

    @Test
    void creationServiceValidationAndExhaustionMapToExpectedStatuses() throws Exception {
        doThrow(new InvalidCreationRequest()).when(service).create("https://example.com", null);
        String body = "{\"url\":\"https://example.com\"}";
        mvc.perform(post("/api/urls").contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value("INVALID_INPUT"));
        doThrow(new UrlService.AllocationExhausted()).when(service).create("https://example.com", null);
        mvc.perform(post("/api/urls").contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.code").value("CODE_ALLOCATION_UNAVAILABLE"));
        doThrow(new IllegalArgumentException("private failure")).when(service).create("https://example.com", null);
        mvc.perform(post("/api/urls").contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isInternalServerError()).andExpect(jsonPath("$.code").value("INTERNAL_ERROR"));
    }

    @ParameterizedTest
    @ValueSource(strings = {"http://127.0.0.1:8000", "http://127.0.0.1:8000/"})
    void rootBaseHasOneSeparator(String base) throws Exception {
        when(service.create("https://example.com", null)).thenReturn(saved(null));
        mvcFor(base).perform(post("/api/urls").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"url\":\"https://example.com\"}"))
                .andExpect(header().string("Location", "http://127.0.0.1:8000/r/Ab12Cd34"));
    }

    @ParameterizedTest
    @ValueSource(strings = {"/relative", "ftp://example.com", "https://user@example.com",
            "https://example.com/?query=1", "https://example.com/#fragment"})
    void rejectsInvalidPublicBase(String base) {
        assertThrows(IllegalArgumentException.class, () -> new UrlController(service, base));
    }
}
