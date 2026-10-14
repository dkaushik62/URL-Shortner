package com.urlshortner.urls;

import jakarta.servlet.RequestDispatcher;
import jakarta.servlet.http.HttpServletRequest;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.Set;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.slf4j.spi.LoggingEventBuilder;

final class RequestEvents {
    static final String ID = RequestEvents.class.getName() + ".id";
    static final String FAILED = RequestEvents.class.getName() + ".failed";
    private static final Logger LOG = LoggerFactory.getLogger(RequestEvents.class);

    private RequestEvents() {}

    static String requestId(HttpServletRequest request) {
        Object existing = request.getAttribute(ID);
        if (existing instanceof String id) return id;
        String id = UUID.randomUUID().toString();
        request.setAttribute(ID, id);
        return id;
    }

    static String path(HttpServletRequest request) {
        Object original = request.getAttribute(RequestDispatcher.ERROR_REQUEST_URI);
        String path = original instanceof String value ? value : request.getRequestURI();
        if (path == null) return "/";
        int query = path.indexOf('?');
        return query < 0 ? path : path.substring(0, query);
    }

    static String operation(HttpServletRequest request) {
        String path = request.getServletPath();
        if (path == null || path.isEmpty()) {
            path = request.getRequestURI();
            String context = request.getContextPath();
            if (path != null && context != null && path.startsWith(context)) {
                path = path.substring(context.length());
            }
        }
        if ("POST".equals(request.getMethod()) && "/api/urls".equals(path)) return "create";
        if ("GET".equals(request.getMethod()) && path != null && path.startsWith("/r/")) return "redirect";
        if ("GET".equals(request.getMethod()) && path != null
                && path.startsWith("/api/urls/") && path.endsWith("/analytics")) return "analytics";
        return "http";
    }

    static void success(HttpServletRequest request, int status) {
        String operation = operation(request);
        if ("http".equals(operation)) return;
        if (!(status == 201 && "create".equals(operation)
                || status == 302 && "redirect".equals(operation)
                || status == 200 && "analytics".equals(operation))) return;
        LoggingEventBuilder event = "analytics".equals(operation) ? LOG.atDebug() : LOG.atInfo();
        event.addKeyValue("requestId", requestId(request))
                .addKeyValue("operation", operation).addKeyValue("outcome", "success")
                .addKeyValue("status", status).log("url_operation");
    }

    static void collision(int attempt) {
        LOG.atDebug().addKeyValue("requestId", MDC.get("requestId"))
                .addKeyValue("operation", "create").addKeyValue("outcome", "collision_retry")
                .addKeyValue("attempt", attempt).log("url_diagnostic");
    }

    static void failure(HttpServletRequest request, ErrorPolicy.Failure failure, Throwable exception) {
        if (Boolean.TRUE.equals(request.getAttribute(FAILED))) return;
        request.setAttribute(FAILED, true);
        LoggingEventBuilder event = failure.unexpected() ? LOG.atError() : LOG.atWarn();
        event.addKeyValue("requestId", requestId(request))
                .addKeyValue("operation", operation(request)).addKeyValue("outcome", "failure")
                .addKeyValue("status", failure.status()).addKeyValue("errorCode", failure.code());
        if (failure.unexpected() && exception != null) {
            event.addKeyValue("diagnostic", diagnostic(exception));
        }
        event.log("url_failure");
    }

    // Never call Throwable.toString(), getMessage(), or pass a Throwable to SLF4J.
    static String diagnostic(Throwable exception) {
        Set<Throwable> seen = Collections.newSetFromMap(new IdentityHashMap<>());
        StringBuilder result = new StringBuilder();
        for (int depth = 0; exception != null && depth < 4 && seen.add(exception); depth++) {
            if (depth > 0) result.append(" <- ");
            result.append(symbol(exception.getClass().getName()));
            StackTraceElement[] frames = exception.getStackTrace();
            for (int i = 0; i < Math.min(4, frames.length); i++) {
                StackTraceElement frame = frames[i];
                result.append(" at ").append(symbol(frame.getClassName())).append('.')
                        .append(symbol(frame.getMethodName())).append(':').append(frame.getLineNumber());
            }
            exception = exception.getCause();
        }
        return result.toString();
    }

    private static String symbol(String value) {
        if (value == null) return "unknown";
        String bounded = value.substring(0, Math.min(value.length(), 120));
        return bounded.replaceAll("[^A-Za-z0-9_.$<>]", "_");
    }
}
