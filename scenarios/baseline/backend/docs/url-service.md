# URL service baseline

POST /api/urls accepts a JSON object with a string `url`. Successful creation returns 201 with `code`, `shortUrl`, `url`, `createdAt` and a Location header pointing to the short URL. The accepted destination is preserved exactly.

Public short URLs use the configured `shortener.public-base-url`, followed by `/r/{code}`. A configured path prefix is retained and trailing slashes are removed before appending the redirect path. Client Host, servlet origin, request context path and forwarded headers do not determine the public URL. The configured base must be an HTTP/HTTPS URL without credentials, control characters, query or fragment; invalid configuration fails application startup. The existing application.yml supplies the property and its environment override.

GET /r/{code} returns 302 with the destination in Location. One schema-qualified PostgreSQL UPDATE increments click_count, sets last_accessed_at and returns the destination. Clients and acceptance checks must disable redirect following to avoid fetching destinations.

GET /api/urls/{code}/analytics returns `code`, `url`, `createdAt`, `clickCount`, `lastAccessedAt`. Initial values are zero and null. Reads do not account for clicks. Timestamps are UTC instants. Unknown codes return 404; invalid creation bodies return 400; five code collisions return 503. Unexpected errors return a generic 500 response.

Validation uses java.net.URI without destination requests or DNS lookups. It requires HTTP or HTTPS, a valid server host and a port in 0..65535 when supplied. Relative URLs, credentials, malformed authority, empty explicit ports, malformed escapes, raw ISO control characters and percent-encoded ISO control characters are rejected. Non-string URL values are rejected. Destinations are never trimmed or rewritten.

Codes contain eight independently selected SecureRandom base62 characters. At most five inserts are attempted without a surrounding transaction. Only SQLSTATE 23505 with structured metadata identifying url_service.urls.pk_urls_code is retried; other failures propagate. Driver diagnostics are accessed reflectively because PostgreSQL is a runtime-only dependency. Error messages are never parsed to infer collisions.

The existing V1 migration creates url_service and url_service.urls and remains unchanged. All service queries are schema-qualified. There is no expiration or rate limiting in this baseline; existing related configuration values do not activate those features.

## Supplied verification evidence

Automated tests: the supplied trusted-runner report for revision 1, source eb14f2c9a4461e52b096a1193154ee33e14071b0, reports a successful Java build and 58 passing JUnit tests with no failures. These results precede the configured-public-base correction. Revised MVC tests have not been executed here. Mock-based tests do not establish live PostgreSQL behavior.

Live acceptance: the same report records passing independent HTTP cases for creation, redirect destination preservation, concurrent accounting, analytics timestamps, unknown links and invalid destinations. The concurrency case reports count 26. This does not establish the 100-redirect procedure below or verify this revision's configured public URL behavior.

Python tests, frontend typecheck and frontend build results were not supplied. No checks were executed during this implementation stage.

## Trusted-runner verification

Use only the trusted Docker runner; never execute generated code on the host. Preserve runner configuration, dependencies and protected acceptance checks. Do not provision cloud services.

Run Java tests using the existing Gradle launcher with `test` in backend. Run Python tests, frontend typecheck and frontend build using the existing runner and manifests. Record each omitted check and its reason. Re-run independent HTTP acceptance for this revision.

1. Use an isolated PostgreSQL database. Confirm Flyway applies the unchanged V1 on a fresh database and inspect constraints and defaults. Verify negative click counts are rejected and real duplicate-code exceptions identify the expected schema, table and constraint.
2. Configure a public base URL reachable by the runner. POST a valid destination with conflicting Host and forwarded headers. Assert 201 and verify both shortUrl and Location use the configured base. Read analytics and assert zero clicks and null lastAccessedAt.
3. Disable redirect following and send 100 concurrent GET requests to the returned short URL. Require every response to be 302 with the exact stored Location. After completion, require clickCount 100 and non-null lastAccessedAt no earlier than createdAt.
4. Repeat analytics reads and verify count and lastAccessedAt remain unchanged. Request unknown redirect and analytics codes, assert 404 and verify no rows were created. Invalid creation requests must also create no rows.
5. Restart against the same database. Confirm Flyway validates unchanged migrations and the destination and analytics survive.
6. Report automated tests separately from live database and HTTP checks. Record request totals, response failures, final persisted count and all omitted checks. Only trusted-runner output establishes execution success.
