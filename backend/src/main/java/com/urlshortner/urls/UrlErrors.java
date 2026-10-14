package com.urlshortner.urls;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class UrlErrors {
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorPolicy.ErrorBody> handle(Exception exception, HttpServletRequest request) {
        return ErrorPolicy.response(request, exception);
    }
}
