package com.urlshortner.urls;

import jakarta.servlet.RequestDispatcher;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.boot.web.servlet.error.ErrorController;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class ServletErrors implements ErrorController {
    @RequestMapping("${server.error.path:${error.path:/error}}")
    public ResponseEntity<ErrorPolicy.ErrorBody> error(HttpServletRequest request, HttpServletResponse response) {
        Object attribute = request.getAttribute(RequestDispatcher.ERROR_STATUS_CODE);
        int status = attribute instanceof Integer value ? value : response.getStatus();
        ErrorPolicy.Failure failure = ErrorPolicy.forStatus(status);
        Object cause = request.getAttribute(RequestDispatcher.ERROR_EXCEPTION);
        RequestEvents.failure(request, failure, cause instanceof Throwable exception ? exception : null);
        if (response.isCommitted()) return null;
        return ResponseEntity.status(failure.status())
                .header("X-Request-ID", RequestEvents.requestId(request))
                .body(ErrorPolicy.body(request, failure));
    }
}
