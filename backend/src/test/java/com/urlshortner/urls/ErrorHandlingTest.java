package com.urlshortner.urls;

import ch.qos.logback.classic.Level;
import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.read.ListAppender;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.DispatcherType;
import jakarta.servlet.RequestDispatcher;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.http.HttpHeaders;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.HttpMediaTypeNotSupportedException;
import org.springframework.web.servlet.resource.NoResourceFoundException;
import org.springframework.http.HttpMethod;
import static org.junit.jupiter.api.Assertions.*;

class ErrorHandlingTest {
    private final ObjectMapper mapper = new ObjectMapper();
    private final Logger logger = (Logger) LoggerFactory.getLogger(RequestEvents.class);
    private final ListAppender<ILoggingEvent> appender = new ListAppender<>();
    private Level previousLevel;
    private Map<String, String> previousMdc;

    @BeforeEach
    void capture() {
        previousLevel = logger.getLevel();
        previousMdc = MDC.getCopyOfContextMap();
        MDC.clear();
        logger.setLevel(Level.DEBUG);
        appender.start();
        logger.addAppender(appender);
    }

    @AfterEach
    void restore() {
        logger.detachAppender(appender);
        appender.stop();
        logger.setLevel(previousLevel);
        if (previousMdc == null) MDC.clear();
        else MDC.setContextMap(previousMdc);
    }

    private MockHttpServletRequest request(String method, String path) {
        MockHttpServletRequest request = new MockHttpServletRequest(method, path);
        request.setServletPath(path);
        request.setQueryString("visitor=PRIVATE_VISITOR");
        request.addHeader("Authorization", "PRIVATE_CREDENTIAL");
        request.addHeader("X-Request-ID", "PRIVATE_VISITOR");
        return request;
    }

    private void envelope(MockHttpServletRequest request, MockHttpServletResponse response,
            int status, String code, String message, Instant before) throws Exception {
        assertEquals(status, response.getStatus());
        assertTrue(response.getContentType().startsWith("application/json"));
        var body = mapper.readTree(response.getContentAsString());
        assertEquals(5, body.size());
        assertEquals(code, body.get("code").asText());
        assertEquals(message, body.get("message").asText());
        assertEquals(RequestEvents.path(request), body.get("path").asText());
        String id = response.getHeader("X-Request-ID");
        UUID.fromString(id);
        assertEquals(id, body.get("requestId").asText());
        assertNotEquals("PRIVATE_VISITOR", id);
        String timestamp = body.get("timestamp").asText();
        assertTrue(timestamp.endsWith("Z"));
        Instant instant = Instant.parse(timestamp);
        assertFalse(instant.isBefore(before));
        assertFalse(instant.isAfter(Instant.now()));
        assertFalse(response.getContentAsString().contains("PRIVATE_"));
    }

    @Test
    void allApplicationErrorsHaveSafeCorrelatedEnvelopesAndRestoreMdc() throws Exception {
        CreationRateLimiter limiter = new CreationRateLimiter(1, () -> 0L);
        limiter.admit();
        Exception limited = assertThrows(CreationRateLimiter.LimitExceeded.class, limiter::admit);
        Exception[] failures = {new InvalidCreationRequest(), new UrlService.UnknownCode(),
                new UrlService.ExpiredCode(), limited, new UrlService.AllocationExhausted(),
                new IllegalArgumentException("PRIVATE_CREDENTIAL https://PRIVATE_DESTINATION", new RuntimeException("PRIVATE_VISITOR"))};
        int[] statuses = {400, 404, 410, 429, 503, 500};
        String[] codes = {"INVALID_INPUT", "LINK_NOT_FOUND", "LINK_EXPIRED", "RATE_LIMITED", "CODE_ALLOCATION_UNAVAILABLE", "INTERNAL_ERROR"};
        String[] messages = {"Invalid creation request", "Unknown code", "Expired code", "Creation limit exceeded", "Code allocation unavailable", "Internal server error"};
        for (int i = 0; i < failures.length; i++) {
            var request = request("GET", "/r/link");
            var response = new MockHttpServletResponse();
            Exception failure = failures[i];
            MDC.put("requestId", "outer");
            MDC.put("worker", "retained");
            Instant before = Instant.now();
            int count = appender.list.size();
            new RequestCorrelationFilter().doFilter(request, response, (req, res) -> {
                assertEquals(request.getAttribute(RequestEvents.ID), MDC.get("requestId"));
                var entity = new UrlErrors().handle(failure, request);
                response.setStatus(entity.getStatusCode().value());
                entity.getHeaders().forEach((name, values) -> values.forEach(value -> response.addHeader(name, value)));
                response.setContentType("application/json");
                response.getWriter().write(mapper.writeValueAsString(entity.getBody()));
            });
            envelope(request, response, statuses[i], codes[i], messages[i], before);
            assertEquals("outer", MDC.get("requestId"));
            assertEquals("retained", MDC.get("worker"));
            assertEquals(count + 1, appender.list.size());
            ILoggingEvent event = appender.list.getLast();
            assertEquals(i == 5 ? Level.ERROR : Level.WARN, event.getLevel());
            assertEquals(response.getHeader("X-Request-ID"), field(event, "requestId"));
            assertEquals("redirect", field(event, "operation"));
            assertEquals("failure", field(event, "outcome"));
            assertEquals(codes[i], field(event, "errorCode"));
            if (i == 3) assertEquals("60", response.getHeader("Retry-After"));
        }
        assertPrivateDataAbsent();
    }

    @Test
    void nativeFrameworkStatusesAndHeadersArePreserved() {
        var request = request("POST", "/other");
        var method = ErrorPolicy.response(request,
                new HttpRequestMethodNotSupportedException("POST", java.util.List.of("GET")));
        assertEquals(405, method.getStatusCode().value());
        assertEquals("GET", method.getHeaders().getFirst(HttpHeaders.ALLOW));
        assertEquals("INVALID_INPUT", method.getBody().code());
        assertEquals(415, ErrorPolicy.response(request,
                new HttpMediaTypeNotSupportedException("private content")).getStatusCode().value());
        assertEquals(404, ErrorPolicy.response(request,
                new NoResourceFoundException(HttpMethod.GET, "PRIVATE_VISITOR")).getStatusCode().value());
        assertPrivateDataAbsent();
    }

    @Test
    void escapingFilterFailureUsesSharedEnvelopeAndCleansContext() throws Exception {
        var request = request("GET", "/r/link");
        var response = new MockHttpServletResponse();
        Instant before = Instant.now();
        new RequestCorrelationFilter().doFilter(request, response, (req, res) -> {
            throw new IllegalStateException("PRIVATE_CREDENTIAL", new RuntimeException("https://PRIVATE_DESTINATION"));
        });
        envelope(request, response, 500, "INTERNAL_ERROR", "Internal server error", before);
        assertNull(MDC.get("requestId"));
        assertEquals(1, appender.list.size());
        assertEquals(Level.ERROR, appender.list.getFirst().getLevel());
        assertPrivateDataAbsent();
    }

    @Test
    void committedFailuresDoNotRewriteBodyOrLogTwiceDuringErrorDispatch() throws Exception {
        var request = request("GET", "/r/link");
        var response = new MockHttpServletResponse();
        new RequestCorrelationFilter().doFilter(request, response, (req, res) -> {
            response.setStatus(302);
            response.getWriter().write("already written");
            response.flushBuffer();
            throw new IllegalStateException("PRIVATE_VISITOR");
        });
        assertEquals(302, response.getStatus());
        assertEquals("already written", response.getContentAsString());
        assertEquals(1, appender.list.size());
        request.setDispatcherType(DispatcherType.ERROR);
        request.setAttribute(RequestDispatcher.ERROR_STATUS_CODE, 500);
        assertNull(new ServletErrors().error(request, response));
        assertEquals(1, appender.list.size());
        assertNull(MDC.get("requestId"));
        assertPrivateDataAbsent();
    }

    @Test
    void servletErrorDispatchRetainsOriginalPathRequestIdAndSingleFailure() throws Exception {
        var request = request("GET", "/error");
        request.setDispatcherType(DispatcherType.ERROR);
        request.setAttribute(RequestDispatcher.ERROR_REQUEST_URI, "/original");
        request.setAttribute(RequestDispatcher.ERROR_STATUS_CODE, 404);
        request.setAttribute(RequestEvents.ID, UUID.randomUUID().toString());
        var response = new MockHttpServletResponse();
        Instant before = Instant.now();
        new RequestCorrelationFilter().doFilter(request, response, (req, res) -> {
            var entity = new ServletErrors().error(request, response);
            response.setStatus(entity.getStatusCode().value());
            response.setContentType("application/json");
            response.getWriter().write(mapper.writeValueAsString(entity.getBody()));
        });
        envelope(request, response, 404, "LINK_NOT_FOUND", "Resource not found", before);
        assertEquals(1, appender.list.size());
        assertNull(MDC.get("requestId"));
    }

    @Test
    void successesAndDiagnosticsRespectConfiguredSeverityAndHaveFixedFields() throws Exception {
        for (String operation : new String[] {"create", "redirect", "analytics"}) {
            String path = operation.equals("create") ? "/api/urls" : operation.equals("redirect") ? "/r/PRIVATE_VISITOR" : "/api/urls/PRIVATE_VISITOR/analytics";
            var request = request(operation.equals("create") ? "POST" : "GET", path);
            var response = new MockHttpServletResponse();
            new RequestCorrelationFilter().doFilter(request, response, (req, res) -> {
                response.setStatus(operation.equals("create") ? 201 : operation.equals("redirect") ? 302 : 200);
            });
            var event = appender.list.getLast();
            assertEquals(operation.equals("analytics") ? Level.DEBUG : Level.INFO, event.getLevel());
            assertEquals(operation, field(event, "operation"));
            assertEquals("success", field(event, "outcome"));
            assertEquals(response.getHeader("X-Request-ID"), field(event, "requestId"));
        }
        MDC.put("requestId", UUID.randomUUID().toString());
        RequestEvents.collision(1);
        assertEquals(Level.DEBUG, appender.list.getLast().getLevel());
        int count = appender.list.size();
        logger.setLevel(Level.INFO);
        RequestEvents.collision(2);
        assertEquals(count, appender.list.size());
        assertPrivateDataAbsent();
    }

    @Test
    void diagnosticTraversalIsBoundedAndCycleSafe() {
        RuntimeException first = new RuntimeException("PRIVATE_CREDENTIAL");
        RuntimeException second = new RuntimeException("PRIVATE_VISITOR");
        first.initCause(second);
        second.initCause(first);
        first.addSuppressed(new RuntimeException("https://PRIVATE_DESTINATION"));
        String diagnostic = RequestEvents.diagnostic(first);
        assertTrue(diagnostic.contains("java.lang.RuntimeException"));
        assertFalse(diagnostic.contains("PRIVATE_"));
        assertTrue(diagnostic.length() < 5000);
    }

    private Object field(ILoggingEvent event, String key) {
        return event.getKeyValuePairs().stream().filter(pair -> pair.key.equals(key))
                .map(pair -> pair.value).findFirst().orElseThrow();
    }

    private void assertPrivateDataAbsent() {
        for (ILoggingEvent event : appender.list) {
            assertNull(event.getThrowableProxy());
            assertFalse(event.getFormattedMessage().contains("PRIVATE_"));
            assertFalse(event.getMDCPropertyMap().toString().contains("PRIVATE_"));
            assertFalse(String.valueOf(event.getKeyValuePairs()).contains("PRIVATE_"));
            assertFalse(String.valueOf(event.getKeyValuePairs()).contains("https://"));
        }
    }
}
