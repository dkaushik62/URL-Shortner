-- Protected disposable V1 fixture. It is never applied to the demo database.
CREATE TABLE public.legacy_upgrade_marker (id INTEGER PRIMARY KEY);
INSERT INTO public.legacy_upgrade_marker VALUES (1);
INSERT INTO url_service.urls (code, url, created_at, click_count, last_accessed_at)
VALUES ('Legacy01', 'https://example.com/legacy', '2026-01-01T00:00:00Z', 7, '2026-01-02T00:00:00Z');
