package com.urlshortner.urls;

import com.fasterxml.jackson.databind.SerializationFeature;
import com.urlshortner.InjectedRedirectFaultFilter;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.http.MediaType;
import org.springframework.http.converter.json.Jackson2ObjectMapperBuilder;
import org.springframework.http.converter.json.MappingJackson2HttpMessageConverter;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.validation.beanvalidation.LocalValidatorFactoryBean;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class ExpiryHttpBoundaryTest {
    private static final Instant T = Instant.parse("2026-01-01T00:00:00.123456789Z");
    private static final String URL = "https://example.com/a?b=1#part";
    private final UrlRepository repository = mock(UrlRepository.class);
    private final CodeGenerator codes = mock(CodeGenerator.class);
    private final Clock clock = mock(Clock.class);
    private final LocalValidatorFactoryBean validator = new LocalValidatorFactoryBean();
    private MockMvc mvc;

    @BeforeEach
    void setup() {
        validator.afterPropertiesSet();
        var mapper = Jackson2ObjectMapperBuilder.json()
                .featuresToDisable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS).build();
        var service = new UrlService(repository, codes, clock, 30);
        mvc = MockMvcBuilders.standaloneSetup(new UrlController(service, "https://public.example/links/"))
                .setControllerAdvice(new UrlErrors()).setValidator(validator)
                .addFilters(new InjectedRedirectFaultFilter())
                .setMessageConverters(new MappingJackson2HttpMessageConverter(mapper)).build();
        when(clock.instant()).thenReturn(T, T.plus(Duration.ofDays(20)));
    }

    @AfterEach
    void close() { validator.close(); }

    @ParameterizedTest
    @ValueSource(longs = {-1, 0, 604800000000001L})
    void invalidBoundariesReturn400BeforeAllocation(long nanos) throws Exception {
        mvc.perform(post("/api/urls").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"url\":\"" + URL + "\",\"expiresAt\":\"" + T.plusNanos(nanos) + "\"}"))
                .andExpect(status().isBadRequest());
        verify(clock).instant();
        verifyNoInteractions(repository, codes);
    }

    @ParameterizedTest
    @ValueSource(longs = {1, 604800000000000L})
    void validBoundariesUseOneInstantAndPreserveFields(long nanos) throws Exception {
        Instant expiry = T.plusNanos(nanos);
        var saved = new UrlRepository.StoredUrl("Ab12Cd34", URL, T, 0, null, expiry);
        when(codes.next()).thenReturn(saved.code());
        when(repository.insert(saved.code(), URL, expiry)).thenReturn(saved);
        mvc.perform(post("/api/urls").header("Host", "attacker.example")
                        .header("Forwarded", "proto=http;host=attacker.example")
                        .header("X-Forwarded-Host", "attacker.example")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"url\":\"" + URL + "\",\"expiresAt\":\"" + expiry + "\"}"))
                .andExpect(status().isCreated())
                .andExpect(header().string("Location", "https://public.example/links/r/Ab12Cd34"))
                .andExpect(jsonPath("$.code").value(saved.code()))
                .andExpect(jsonPath("$.shortUrl").value("https://public.example/links/r/Ab12Cd34"))
                .andExpect(jsonPath("$.url").value(URL))
                .andExpect(jsonPath("$.createdAt").value(T.toString()))
                .andExpect(jsonPath("$.expiresAt").value(expiry.toString()));
        verify(clock).instant();
        verify(repository).insert(saved.code(), URL, expiry);
    }
}
