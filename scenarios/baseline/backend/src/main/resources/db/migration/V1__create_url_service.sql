CREATE SCHEMA IF NOT EXISTS url_service;

CREATE TABLE url_service.urls (
    code VARCHAR(8) NOT NULL,
    url TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    click_count BIGINT NOT NULL DEFAULT 0,
    last_accessed_at TIMESTAMPTZ,
    CONSTRAINT pk_urls_code PRIMARY KEY (code),
    CONSTRAINT ck_urls_click_count CHECK (click_count >= 0)
);
