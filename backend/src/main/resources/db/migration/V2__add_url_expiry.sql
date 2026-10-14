ALTER TABLE url_service.urls
    ADD COLUMN expires_at TIMESTAMPTZ,
    ADD COLUMN expires_at_submicro SMALLINT,
    ADD CONSTRAINT ck_urls_expiry_precision CHECK (
        (expires_at IS NULL AND expires_at_submicro IS NULL)
        OR (expires_at IS NOT NULL AND expires_at_submicro IS NOT NULL
            AND expires_at_submicro BETWEEN 0 AND 999)
    );
