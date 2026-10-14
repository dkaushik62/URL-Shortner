package com.urlshortner.urls;

import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice(assignableTypes = UrlController.class)
public class UrlErrors {
    public record ErrorBody(String error) {}

    @ExceptionHandler(CreationRateLimiter.LimitExceeded.class)
    public ResponseEntity<ErrorBody> limited(CreationRateLimiter.LimitExceeded exception) {
        return ResponseEntity.status(429)
                .header("Retry-After", Long.toString(exception.retryAfter()))
                .body(new ErrorBody("Creation limit exceeded"));
    }

    @ExceptionHandler({MethodArgumentNotValidException.class, HttpMessageNotReadableException.class, IllegalArgumentException.class})
    public ResponseEntity<ErrorBody> invalid(Exception exception) {
        return ResponseEntity.badRequest().body(new ErrorBody("Invalid creation request"));
    }

    @ExceptionHandler(UrlService.UnknownCode.class)
    public ResponseEntity<ErrorBody> missing() {
        return ResponseEntity.status(404).body(new ErrorBody("Unknown code"));
    }

    @ExceptionHandler(UrlService.ExpiredCode.class)
    public ResponseEntity<ErrorBody> expired() {
        return ResponseEntity.status(410).body(new ErrorBody("Expired code"));
    }

    @ExceptionHandler(UrlService.AllocationExhausted.class)
    public ResponseEntity<ErrorBody> exhausted() {
        return ResponseEntity.status(503).body(new ErrorBody("Code allocation unavailable"));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorBody> internal(Exception exception) {
        return ResponseEntity.internalServerError().body(new ErrorBody("Internal server error"));
    }
}
