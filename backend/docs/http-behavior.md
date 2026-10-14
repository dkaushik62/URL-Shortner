# URL service HTTP behavior

## Creation

`POST /api/urls` accepts an object with required textual `url` and optional `expiresAt`. Creation returns 201 with `code`, `shortUrl`, `url`, `createdAt`, and explicitly nullable `expiresAt`. `Location` and `shortUrl` use only `shortener.public-base-url`; trailing slashes are removed and configured path prefixes are preserved. Client Host and forwarded headers do not determine public URLs.

Destinations must be absolute HTTP/HTTPS URIs with a valid host and port. Credentials, malformed escapes, raw controls, encoded controls, empty explicit ports, and ports above 65535 are rejected. Validation makes no destination network request.

Omitted or null expiry means no expiration. Supplied expiry must be ISO-8601 text with UTC offset (`Z` or `+00:00`). It must be strictly later than one captured service clock instant and no later than `min(shortener.max-expiry-days, 7)` days afterward. The upper boundary is inclusive. Smaller positive settings impose a stricter maximum; nonpositive settings fail startup. The configured default of 30 days remains capped at seven. Invalid input is rejected before allocation after creation admission.

## Redirects and analytics

`GET /r/{code}` returns 302 and the exact stored destination in Location. Each eligible redirect atomically increments clickCount once and updates lastAccessedAt. Unknown links return 404; expiry equal to or earlier than the captured evaluation instant returns 410. These failures have no Location and do not update accounting. Disable redirect following when verifying HTTP responses.

`GET /api/urls/{code}/analytics` returns 200 with code, url, createdAt, clickCount, lastAccessedAt, and explicitly nullable expiresAt. Analytics remains readable after expiry and never mutates redirect accounting. Unknown links return 404.

## Creation allowance

`shortener.creation-limit-per-minute` defaults to 20 and accepts positive integer overrides. A shared process-local limiter admits that many attempts in a fixed 60-second monotonic window beginning with the first admitted attempt. Admission precedes body conversion and validation. Malformed bodies, rejected input, and failed creations consume allowance; collision retries do not consume additional slots.

Excess attempts return 429 with Retry-After equal to the remaining window seconds rounded upward, at least one. Rejection does not extend the window or allocate codes/write rows. A new allowance is available at exactly 60 seconds. Redirects and analytics remain available. The limiter stores no visitor identifiers, resets on restart, and is independent in each instance. Fixed windows can admit twice the allowance across a boundary.

## Error contract

All application errors use these five fields:

```json
{"code":"INVALID_INPUT","message":"Invalid creation request","timestamp":"2026-10-15T00:00:00Z","path":"/api/urls","requestId":"1b956bd9-55f3-4f89-9106-0c0bb66e7d83"}
```

Timestamp is UTC ISO-8601 text independent of Jackson date serialization settings. Path is the request URI without a query string, or the original URI during servlet error dispatch. Request ID matches X-Request-ID. Every request receives a server-generated UUID; incoming IDs are ignored. IDs persist during error dispatch and appear in application events. Previous MDC state is restored when request processing exits.

| Code | HTTP status | Client message |
| --- | --- | --- |
| INVALID_INPUT | 400 | Invalid creation request |
| LINK_NOT_FOUND | 404 | Unknown code |
| LINK_EXPIRED | 410 | Expired code |
| RATE_LIMITED | 429 | Creation limit exceeded |
| CODE_ALLOCATION_UNAVAILABLE | 503 | Code allocation unavailable |
| INTERNAL_ERROR | 500 | Internal server error |

Allocation retains five attempts and the existing recognized PostgreSQL collision policy. Rate limiting retains Retry-After. Malformed JSON, Jakarta input validation failures, destination validation, and expiry validation produce INVALID_INPUT. Unrelated IllegalArgumentException failures produce INTERNAL_ERROR.

Framework errors preserve their status and supplied protocol headers, including Allow. Other client protocol errors use INVALID_INPUT with `Invalid HTTP request`; unrelated missing resources use LINK_NOT_FOUND with `Resource not found`. Framework or servlet server errors retain their status with INTERNAL_ERROR and the generic message. Internal exception messages never enter error bodies.

The MVC advice owns controller exception handling. The correlation filter handles exceptions escaping MVC; the servlet error controller handles error dispatch. A request attribute prevents duplicate application failure events. Once a response is committed, its body and status cannot be replaced; only a safe failure event is recorded.

## Verification

Automated tests: no trusted results for this enhancement were supplied. Python tests, frontend typecheck/build, and Java tests were not executed by this stage.

Live runs: PostgreSQL and independent HTTP acceptance were not executed by this stage. Mocked and servlet fixture tests do not establish live behavior. Run generated code only through the trusted Docker runner and record actual results separately. Existing migrations and protected acceptance checks remain unchanged.
