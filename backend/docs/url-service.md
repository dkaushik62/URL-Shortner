# URL service

The Java service retains JdbcTemplate storage and the API behavior documented in http-behavior.md. Creation uses url and returns code, shortUrl, url, createdAt, and explicitly nullable expiresAt. Public URLs use shortener.public-base-url exclusively. Redirects return 302 for eligible links and atomically account for clicks. Analytics uses clickCount and remains readable after expiry without mutating accounting.

Expiry is optional. Supplied UTC expiry must be strictly in the future and at most min(shortener.max-expiry-days, 7) days from one captured Clock instant, inclusive at the maximum. Nonpositive configuration fails startup. Creation admission remains before body conversion and validation, using the shared configured allowance (default 20 per minute). Failures consume admitted slots; collision retries do not.

Existing protected migrations remain unchanged. V1 creates url_service and its urls table; V2 adds nullable expires_at and expires_at_submicro. Existing rows remain non-expiring. JdbcTemplate queries remain schema-qualified. Expiry is truncated to microseconds for timestamp binding and its remaining 0..999 nanoseconds stored separately. Reads reconstruct exact expiry. Atomic redirect SQL uses strict lexicographic greater-than for eligibility. last_accessed_at retains microsecond precision.

Eight-character SecureRandom base62 codes retain five allocation attempts. Only structured PostgreSQL SQLSTATE 23505 metadata identifying url_service.urls.pk_urls_code permits retries. InjectedRedirectFaultFilter remains a pass-through filter.

## Central errors and correlation

The stable catalogue is INVALID_INPUT/400, LINK_NOT_FOUND/404, LINK_EXPIRED/410, RATE_LIMITED/429, CODE_ALLOCATION_UNAVAILABLE/503, and INTERNAL_ERROR/500. The complete safe-message catalogue and framework status policy are in http-behavior.md. Bodies contain code, message, UTC ISO-8601 timestamp, path without query, and requestId. RATE_LIMITED retains Retry-After.

RequestCorrelationFilter runs at highest precedence, ahead of the existing redirect filter. It generates a server-owned UUID, ignores incoming correlation headers, returns X-Request-ID, and binds requestId to MDC. Error dispatch reuses the request attribute. Previous MDC state is restored in finally.

UrlErrors is the central MVC handler. ErrorPolicy supplies classification and envelopes to MVC, filter, and servlet error paths. InvalidCreationRequest extends IllegalArgumentException so existing service validation assertions remain valid while unrelated programming errors become 500. Framework ErrorResponse status and headers are preserved. RequestEvents owns application failure events and uses a request marker to suppress duplicate failure logging. Repositories and service failures propagate without logging the exception again.

Committed responses cannot be rewritten. The filter records a single safe failure event and leaves the committed response intact. Exact servlet container behavior and registration must be checked by the trusted runner; standalone MockMvc is insufficient to establish container error dispatch.

## Structured application events

SLF4J key-value events use requestId, operation, outcome, and status, plus errorCode for failures. Operation comes from fixed endpoint categories: create, redirect, analytics, or http. Raw paths and link codes are excluded from logs.

- INFO: successful creation and redirect.
- DEBUG: successful analytics and recognized collision retry diagnostics.
- WARN: recoverable client errors and allocation exhaustion.
- ERROR: unexpected failures.

Unexpected failure diagnostics retain bounded exception class names and up to four frames per cause, across at most four cycle-safe causes. No original Throwable is supplied to the logger. Messages, suppressed exceptions, SQL exception messages, SQL text, destination URLs, request bodies, headers, cookies, credentials, visitor identifiers, and link codes are excluded from application events. Collision events include only an attempt number and request correlation. Diagnostics for direct non-HTTP service calls may have no requestId.

## Logging configuration

Use existing Spring Boot configuration mechanisms without changing application.yml. The package level defaults through Boot's normal configuration and can be set externally:

```properties
logging.level.com.urlshortner=INFO
```

Enable application diagnostics with an environment variable:

```text
LOGGING_LEVEL_COM_URLSHORTNER=DEBUG
```

Or supply a command-line override:

```text
java -jar app.jar --logging.level.com.urlshortner=DEBUG
```

Spring Boot 3.5 also supports optional built-in structured console output:

```text
java -jar app.jar --logging.structured.format.console=logstash --logging.level.com.urlshortner=INFO
```

The same format can be configured with LOGGING_STRUCTURED_FORMAT_CONSOLE=logstash. Plain console logging retains SLF4J key-value pairs; structured formatting makes the fields easier for operators to consume. No logging dependencies are added.

Prefer package-scoped diagnostics. Enabling framework web, JDBC, or root DEBUG/TRACE can independently log sensitive request or database data and is outside the sanitization policy of these application events. Do not collect or commit raw provider logs, credentials, tokens, or runtime databases.

## Verification status

Automated tests: no tests were executed by this implementation stage and no trusted results for this enhancement were supplied. Java compilation/tests, Python tests, and frontend typecheck/build remain outstanding. Existing supplied historical results described 100 Java tests with 98 passing and two fixture failures for source 528696c0e0e6b167c2fb340a164bc45490790427; those results do not verify this revision.

The CreationLimitHttpTest fixture retains its BeanFactoryPostProcessor registration fix and behavioral assertions while installing request correlation and updating error-body assertions. Existing expiry, public URL, limiter concurrency, repository precision, and service regression tests remain applicable. New ErrorHandlingTest covers shared envelopes, application codes, native framework status/headers, escaping failures, committed responses, servlet error fixtures, MDC restoration, structured severity, and sensitive exception sentinels. Mocked and servlet fixture coverage does not establish live PostgreSQL or container behavior.

Live runs: no live PostgreSQL or independent HTTP results were supplied or executed. Migration compatibility, exact database round trips, allowance recovery, container dispatch, and concurrent accounting remain unverified.

## Trusted-runner checks

1. Execute Python tests, frontend typecheck/build, and Java tests using the trusted Docker runner. Record revision, actual outcomes, and omissions separately from live runs.
2. Run unchanged independent HTTP acceptance with redirect following disabled. Verify the new envelopes, all statuses and headers, supplied-ID replacement, filter ordering, and actual servlet error dispatch.
3. Verify fresh V1/V2 migrations, populated V1 upgrade, unchanged checksums, nullable expiry, and exact nanosecond round trips for remainders 0, 1, 789, and 999.
4. Verify inclusive seven-day and stricter configured expiry boundaries using a trusted controllable Clock. Record unavailable fixtures explicitly. Check public URL prefixes despite conflicting client headers.
5. In an isolated live window, issue 100 concurrent creation attempts: exactly 20 should return 201 and 80 return 429, with 20 inserted rows. Mark runs crossing a window boundary inconclusive. Verify malformed admission, recovery, positive overrides, and restart reset.
6. Verify redirects and analytics remain usable after allowance exhaustion. Issue 100 successful concurrent redirects and verify clickCount increases by 100; analytics must not mutate accounting.
7. Inspect isolated application events for correlation, severity, one failure event per request, and absence of sensitive sentinels. Test doubles must not be described as successful live runs.
