package com.urlshortner.urls;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.DispatcherType;
import jakarta.servlet.FilterChain;
import jakarta.servlet.RequestDispatcher;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.Map;
import org.slf4j.MDC;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class RequestCorrelationFilter extends OncePerRequestFilter {
    private final ObjectMapper mapper = new ObjectMapper();

    @Override
    protected boolean shouldNotFilterErrorDispatch() { return false; }

    @Override
    protected void doFilterNestedErrorDispatch(HttpServletRequest request, HttpServletResponse response,
            FilterChain chain) throws ServletException, IOException {
        correlated(request, response, chain);
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
            FilterChain chain) throws ServletException, IOException {
        correlated(request, response, chain);
    }

    private void correlated(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        Map<String, String> previous = MDC.getCopyOfContextMap();
        String id = RequestEvents.requestId(request);
        MDC.put("requestId", id);
        if (!response.isCommitted()) response.setHeader("X-Request-ID", id);
        try {
            chain.doFilter(request, response);
            if (response.getStatus() >= 400 && !Boolean.TRUE.equals(request.getAttribute(RequestEvents.FAILED))) {
                ErrorPolicy.Failure failure = ErrorPolicy.forStatus(response.getStatus());
                RequestEvents.failure(request, failure, null);
                if (request.getDispatcherType() == DispatcherType.ERROR && !response.isCommitted()) {
                    write(request, response, failure);
                }
            } else if (request.getDispatcherType() == DispatcherType.REQUEST
                    && !Boolean.TRUE.equals(request.getAttribute(RequestEvents.FAILED))) {
                RequestEvents.success(request, response.getStatus());
            }
        } catch (Exception exception) {
            ErrorPolicy.Failure failure = ErrorPolicy.forStatus(500);
            RequestEvents.failure(request, failure, exception);
            if (!response.isCommitted()) {
                write(request, response, failure);
            }
            // A committed response cannot be replaced. Its single failure event is retained.
        } finally {
            if (previous == null) MDC.clear();
            else MDC.setContextMap(previous);
        }
    }

    private void write(HttpServletRequest request, HttpServletResponse response, ErrorPolicy.Failure failure)
            throws IOException {
        response.resetBuffer();
        response.setStatus(failure.status());
        response.setHeader("Location", null);
        response.setHeader("X-Request-ID", RequestEvents.requestId(request));
        response.setCharacterEncoding("UTF-8");
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.getWriter().write(mapper.writeValueAsString(ErrorPolicy.body(request, failure)));
    }
}
