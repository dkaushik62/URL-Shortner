# URL service

POST /api/urls accepts a string url and optional expiresAt. Omitted or JSON null expiry means no expiration. Supplied expiry must be ISO-8601 text with UTC offset, strictly later than one captured injected Clock instant and at most the smaller of shortener.max-expiry-days and seven days after it. Exactly the effective maximum is accepted. Nonpositive configuration is rejected at startup. The application.yml default of 30 is capped at seven by the service; the service property fallback is seven. UTC Z and +00:00 are accepted. Invalid expiry returns 400 before code allocation when admission succeeds.

Creation returns 201 with code, shortUrl, url, createdAt and explicitly nullable expiresAt. Location and shortUrl use shortener.public-base-url, preserving configured path prefixes and ignoring client Host and forwarded headers. Analytics returns code, url, createdAt, clickCount, lastAccessedAt and explicitly nullable expiresAt, including after expiration. Analytics never increments counters.

GET /r/{code} returns 302 with the exact destination only when eligible at its captured Clock instant. Unknown links return 404. Expiry equal to or earlier than that instant returns 410 without Location. A schema-qualified PostgreSQL conditional UPDATE increments click_count once and sets last_accessed_at only for eligible links. A failed update is followed by a read to distinguish unknown from expired. InjectedRedirectFaultFilter passes responses through. Independent HTTP verification must disable redirect following.

Existing protected migrations remain unchanged. V1 creates url_service and its urls table. V2 adds nullable expires_at and expires_at_submicro. Existing rows remain non-expiring. Expiry is truncated to microseconds before JDBC binding, with its remaining 0..999 nanoseconds stored separately. Reads reconstruct the exact Instant. Redirect SQL compares timestamp and remainder lexicographically with strict greater-than. last_accessed_at records the captured evaluation time at microsecond precision.

Destination validation accepts HTTP/HTTPS destinations and rejects invalid hosts or ports, credentials, malformed escapes and raw or encoded controls. No destination network requests are made. Eight-character SecureRandom base62 codes retain five allocation attempts. Only structured PostgreSQL SQLSTATE 23505 metadata identifying url_service.urls.pk_urls_code permits retries. Unexpected failures return generic 500 responses; allocation exhaustion returns 503.

## Local creation allowance

shortener.creation-limit-per-minute defaults to 20 and must be a positive integer; invalid configuration fails startup. One shared bucket covers creation attempts through this single local instance. It does not distinguish remote clients. Host, forwarded headers, addresses and cookies do not select buckets.

A synchronized admission operation uses System.nanoTime and starts a fixed 60-second window on the first attempt. The first configured number of attempts are admitted. Excess attempts return 429 with a generic error body and Retry-After containing the ceiling number of remaining seconds, at least one. At exactly 60 seconds a fresh allowance becomes available. Rejected attempts do not extend the window. Fixed windows permit up to twice the allowance across a boundary.

The MVC interceptor runs after handler selection and before request-body conversion and validation. Malformed JSON, invalid destinations or expiry, allocation failures and database failures consume admission. Internal collision retries consume no additional slots. Rejected attempts perform no code allocation or repository writes. The lock is released before body processing, validation or database work. Redirects, analytics and unrelated handlers neither consume allowance nor receive limiter responses.

Only a window start and bounded admitted counter are retained as temporary rate-limit state. No visitor identifiers are collected or stored by the limiter. State resets on process restart. All bridge callers can share the allowance, and one caller can exhaust it. Multiple instances would have independent state. This creation limit does not bound in-flight concurrency or establish distributed scaling, an availability SLA or production benchmark results.

## Verification status

Automated tests: supplied trusted-runner results for source 528696c0e0e6b167c2fb340a164bc45490790427 on 2026-10-14 show successful Java compilation and 100 executed Java tests, with 98 passing and 2 failing. Both failures occurred in CreationLimitHttpTest before HTTP assertions because its fixture accessed the BeanFactory before context refresh. The recovery and endpoint-isolation cases therefore did not establish their intended outcomes.

This replacement registers injected limiters through a BeanFactoryPostProcessor during refresh and retains the HTTP assertions and configuration coverage. No tests were executed by this implementation stage, and no runner results for these replacements are available. Existing expiry, public URL and JDBC tests remain unchanged. Mocked repository checks do not establish PostgreSQL behavior.

Live runs: no live PostgreSQL or independent HTTP acceptance results were supplied or executed by this stage. Migration compatibility, exact database timestamp round trips, live allowance recovery and concurrent accounting remain unverified.

Python tests and frontend typecheck/build results were not supplied. Java tests must be rerun for these replacements; independent HTTP acceptance remains outstanding. Execute generated code only through the trusted Docker runner. Replacements are confined to backend/src/ and backend/docs/; protected platform files and existing migrations remain unchanged.

## Trusted-runner checks

1. Run Python tests, frontend typecheck/build and Java tests using existing runner commands. Record source revision, actual results and omissions separately from live runs. Confirm both repaired HTTP cases execute their existing assertions.
2. Verify fresh V1/V2 migration, populated V1 upgrade and unchanged Flyway checksums. Check null expiry and exact nanosecond round trips for remainders 0, 1, 789 and 999, including rollover.
3. Verify seven-day inclusive boundaries, stricter configured expiry, omitted/null expiry, configured public URL path prefixes and conflicting client headers. Use a trusted controllable Clock for exact expiry equality; report unavailable fixtures explicitly.
4. In a fresh isolated live instance, disable redirect following. Verify 20 creations return 201, excess attempts return 429 with positive Retry-After, and row count increases by exactly 20. Verify malformed attempts consume allowance without insertion, positive overrides, actual window recovery and restart reset.
5. Verify concurrent creation counts within one window. Mark a run inconclusive if it crosses a boundary. After exhaustion verify redirects and analytics remain available, including 404 and 410 behavior. Verify 100 successful concurrent redirects increase clickCount by 100; analytics reads must not mutate accounting.
