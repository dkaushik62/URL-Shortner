package com.urlshortner.urls;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.method.HandlerMethod;
import org.springframework.web.servlet.HandlerInterceptor;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration(proxyBeanMethods = false)
public class CreationLimitConfiguration implements WebMvcConfigurer {
    private final CreationRateLimiter limiter;

    public CreationLimitConfiguration(CreationRateLimiter limiter) {
        this.limiter = limiter;
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(new HandlerInterceptor() {
            @Override
            public boolean preHandle(HttpServletRequest request, HttpServletResponse response,
                    Object handler) {
                if (handler instanceof HandlerMethod method
                        && UrlController.class.isAssignableFrom(method.getBeanType())
                        && method.getMethod().getName().equals("create")
                        && method.getMethod().getParameterCount() == 1
                        && method.getMethod().getParameterTypes()[0] == UrlController.CreateRequest.class) {
                    limiter.admit();
                }
                return true;
            }
        });
    }
}
