package com.urlshortner.urls;

import jakarta.servlet.http.HttpServletRequest;
import java.time.Instant;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.ErrorResponse;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.ServletRequestBindingException;
import org.springframework.web.method.annotation.HandlerMethodValidationException;
import jakarta.validation.ConstraintViolationException;

final class ErrorPolicy {
    record ErrorBody(String code, String message, String timestamp, String path, String requestId) {}
    record Failure(int status, String code, String message, boolean unexpected) {}

    private ErrorPolicy() {}

    static Failure classify(Throwable exception) {
        if (exception instanceof InvalidCreationRequest
                || exception instanceof MethodArgumentNotValidException
                || exception instanceof HttpMessageNotReadableException
                || exception instanceof ConstraintViolationException
                || exception instanceof HandlerMethodValidationException validation && !validation.isForReturnValue()
                || exception instanceof ServletRequestBindingException) {
            return new Failure(400, "INVALID_INPUT", "Invalid creation request", false);
        }
        if (exception instanceof UrlService.UnknownCode) {
            return new Failure(404, "LINK_NOT_FOUND", "Unknown code", false);
        }
        if (exception instanceof UrlService.ExpiredCode) {
            return new Failure(410, "LINK_EXPIRED", "Expired code", false);
        }
        if (exception instanceof CreationRateLimiter.LimitExceeded) {
            return new Failure(429, "RATE_LIMITED", "Creation limit exceeded", false);
        }
        if (exception instanceof UrlService.AllocationExhausted) {
            return new Failure(503, "CODE_ALLOCATION_UNAVAILABLE", "Code allocation unavailable", false);
        }
        if (exception instanceof ErrorResponse response) return forStatus(response.getStatusCode().value());
        return forStatus(500);
    }

    static Failure forStatus(int status) {
        if (status < 400 || status > 599) status = 500;
        if (status >= 500) return new Failure(status, "INTERNAL_ERROR", "Internal server error", true);
        if (status == 404) return new Failure(status, "LINK_NOT_FOUND", "Resource not found", false);
        if (status == 410) return new Failure(status, "LINK_EXPIRED", "Expired code", false);
        if (status == 429) return new Failure(status, "RATE_LIMITED", "Creation limit exceeded", false);
        return new Failure(status, "INVALID_INPUT", "Invalid HTTP request", false);
    }

    static ErrorBody body(HttpServletRequest request, Failure failure) {
        return new ErrorBody(failure.code(), failure.message(), Instant.now().toString(),
                RequestEvents.path(request), RequestEvents.requestId(request));
    }

    static ResponseEntity<ErrorBody> response(HttpServletRequest request, Throwable exception) {
        Failure failure = classify(exception);
        RequestEvents.failure(request, failure, exception);
        HttpHeaders headers = new HttpHeaders();
        if (exception instanceof ErrorResponse framework) headers.putAll(framework.getHeaders());
        headers.set("X-Request-ID", RequestEvents.requestId(request));
        if (exception instanceof CreationRateLimiter.LimitExceeded limited) {
            headers.set("Retry-After", Long.toString(limited.retryAfter()));
        }
        return ResponseEntity.status(failure.status()).headers(headers).body(body(request, failure));
    }
}
