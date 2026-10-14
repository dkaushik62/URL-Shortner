package com.urlshortner.urls;

import com.urlshortner.InjectedRedirectFaultFilter;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Test;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockServletContext;
import org.springframework.test.context.support.TestPropertySourceUtils;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.support.AnnotationConfigWebApplicationContext;
import org.springframework.web.servlet.config.annotation.EnableWebMvc;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class CreationLimitHttpTest {
    private static final Instant NOW = Instant.parse("2026-01-01T00:00:00Z");
    private static final String URL = "https://example.com";
    private static final String BODY = "{\"url\":\"https://example.com\"}";

    @Configuration(proxyBeanMethods = false)
    @EnableWebMvc
    @Import({CreationLimitConfiguration.class, UrlErrors.class, RequestCorrelationFilter.class, ServletErrors.class})
    static class WebConfig {
        @Bean UrlRepository repository() { return mock(UrlRepository.class); }
        @Bean CodeGenerator codes() { return mock(CodeGenerator.class); }
        @Bean UrlService service(UrlRepository repository, CodeGenerator codes) {
            return new UrlService(repository, codes, Clock.fixed(NOW, ZoneOffset.UTC), 30);
        }
        @Bean UrlController controller(UrlService service) {
            return new UrlController(service, "https://public.example/links/");
        }
    }

    private AnnotationConfigWebApplicationContext context(String property, CreationRateLimiter limiter) {
        var context = new AnnotationConfigWebApplicationContext();
        context.setServletContext(new MockServletContext());
        if (property != null) TestPropertySourceUtils.addInlinedPropertiesToEnvironment(context,
                "shortener.creation-limit-per-minute=" + property);
        if (limiter == null) context.register(CreationRateLimiter.class);
        else context.addBeanFactoryPostProcessor(factory -> factory.registerSingleton("creationRateLimiter", limiter));
        context.register(WebConfig.class);
        return context;
    }

    private MockMvc mvc(AnnotationConfigWebApplicationContext context) {
        return MockMvcBuilders.webAppContextSetup(context)
                .addFilters(context.getBean(RequestCorrelationFilter.class), new InjectedRedirectFaultFilter()).build();
    }

    @Test
    void registeredInterceptorUsesDefaultAndPropertyOverridesBeforeWrites() throws Exception {
        for (String property : new String[] {null, "1", "3"}) {
            try (var context = context(property, null)) {
                context.refresh();
                MockMvc mvc = mvc(context);
                var repository = context.getBean(UrlRepository.class);
                var codes = context.getBean(CodeGenerator.class);
                when(codes.next()).thenReturn("Ab12Cd34");
                when(repository.insert("Ab12Cd34", URL, null)).thenReturn(
                        new UrlRepository.StoredUrl("Ab12Cd34", URL, NOW, 0, null, null));
                int limit = property == null ? 20 : Integer.parseInt(property);
                for (int i = 0; i < limit; i++) {
                    mvc.perform(post("/app/api/urls").contextPath("/app")
                                    .header("Host", "caller" + i + ".example")
                                    .header("X-Forwarded-For", "192.0.2." + i)
                                    .contentType(MediaType.APPLICATION_JSON).content(BODY))
                            .andExpect(status().isCreated())
                            .andExpect(jsonPath("$.shortUrl").value("https://public.example/links/r/Ab12Cd34"));
                }
                clearInvocations(repository, codes);
                mvc.perform(post("/api/urls").contentType(MediaType.APPLICATION_JSON).content(BODY))
                        .andExpect(status().isTooManyRequests())
                        .andExpect(header().string("Retry-After", org.hamcrest.Matchers.matchesPattern("[1-9][0-9]*")))
                        .andExpect(header().doesNotExist("Location"))
                        .andExpect(jsonPath("$.code").value("RATE_LIMITED"))
                        .andExpect(jsonPath("$.message").value("Creation limit exceeded"))
                        .andExpect(result -> {
                            var body = new com.fasterxml.jackson.databind.ObjectMapper()
                                    .readTree(result.getResponse().getContentAsString());
                            assertEquals(result.getResponse().getHeader("X-Request-ID"), body.get("requestId").asText());
                            assertEquals("/api/urls", body.get("path").asText());
                            Instant.parse(body.get("timestamp").asText());
                        });
                verifyNoInteractions(repository, codes);
            }
        }
    }

    @Test
    void invalidConfigurationFailsContextInitialization() {
        for (String property : new String[] {"0", "-1", "nonnumeric"}) {
            try (var context = context(property, null)) {
                assertThrows(RuntimeException.class, context::refresh);
            }
        }
    }

    @Test
    void invalidAttemptsConsumeAllowanceAndRecoveryUsesMonotonicTime() throws Exception {
        AtomicLong time = new AtomicLong();
        try (var context = context(null, new CreationRateLimiter(3, time::get))) {
            context.refresh();
            MockMvc mvc = mvc(context);
            var repository = context.getBean(UrlRepository.class);
            var codes = context.getBean(CodeGenerator.class);
            for (String body : new String[] {"{", "{\"url\":42}",
                    "{\"url\":\"https://example.com\",\"expiresAt\":\"bad\"}"}) {
                mvc.perform(post("/api/urls").contentType(MediaType.APPLICATION_JSON).content(body))
                        .andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value("INVALID_INPUT"));
            }
            mvc.perform(post("/api/urls").contentType(MediaType.APPLICATION_JSON).content("{"))
                    .andExpect(status().isTooManyRequests()).andExpect(header().string("Retry-After", "60"));
            verifyNoInteractions(repository, codes);
            time.set(60_000_000_000L);
            mvc.perform(post("/api/urls").contentType(MediaType.APPLICATION_JSON).content("{"))
                    .andExpect(status().isBadRequest()).andExpect(header().doesNotExist("Retry-After"));
        }
    }

    @Test
    void redirectsAndAnalyticsRemainUnlimitedAndDoNotConsumeAllowance() throws Exception {
        try (var context = context(null, new CreationRateLimiter(1, () -> 0L))) {
            context.refresh();
            MockMvc mvc = mvc(context);
            var repository = context.getBean(UrlRepository.class);
            when(repository.recordRedirect("valid", NOW)).thenReturn(Optional.of(URL));
            when(repository.find("valid")).thenReturn(Optional.of(
                    new UrlRepository.StoredUrl("valid", URL, NOW, 0, null, null)));
            when(repository.find("expired")).thenReturn(Optional.of(
                    new UrlRepository.StoredUrl("expired", URL, NOW, 0, null, NOW)));
            for (int phase = 0; phase < 2; phase++) {
                for (int i = 0; i < 25; i++) {
                    mvc.perform(get("/r/valid")).andExpect(status().isFound())
                            .andExpect(header().string("Location", URL))
                            .andExpect(header().doesNotExist("Retry-After"));
                    mvc.perform(get("/api/urls/valid/analytics")).andExpect(status().isOk())
                            .andExpect(jsonPath("$.clickCount").value(0))
                            .andExpect(header().doesNotExist("Retry-After"));
                }
                if (phase == 0) {
                    mvc.perform(post("/api/urls").contentType(MediaType.APPLICATION_JSON).content("{"))
                            .andExpect(status().isBadRequest());
                }
            }
            mvc.perform(post("/api/urls").contentType(MediaType.APPLICATION_JSON).content(BODY))
                    .andExpect(status().isTooManyRequests());
            mvc.perform(get("/r/expired")).andExpect(status().isGone())
                    .andExpect(header().doesNotExist("Retry-After"));
            mvc.perform(get("/r/missing")).andExpect(status().isNotFound());
            mvc.perform(get("/api/urls/missing/analytics")).andExpect(status().isNotFound());
        }
    }
}
