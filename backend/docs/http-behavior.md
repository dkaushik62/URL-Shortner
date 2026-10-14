# Existing URL service HTTP behavior

This page describes the supplied Java implementation. Requests and responses use the existing field names and error bodies.

## Create a link

`POST /api/urls` accepts a JSON object with required string `url` and optional `expiresAt`:

```json
{"url":"https://example.com/a?b=1#part"}
```

Successful creation returns **201 Created**, a `Location` header containing the public short URL, and these JSON fields:

- `code`: generated eight-character base62 code.
- `shortUrl`: public short URL.
- `url`: stored destination.
- `createdAt`: stored creation timestamp.
- `expiresAt`: expiry timestamp, explicitly `null` for a non-expiring link.

For example, with `shortener.public-base-url=http://127.0.0.1:8000`, a generated code `Ab12Cd34` produces `http://127.0.0.1:8000/r/Ab12Cd34` in both `shortUrl` and `Location`. Trailing slashes are removed from the configured base; configured path prefixes are preserved. Client `Host`, `Forwarded` and `X-Forwarded-*` headers do not determine these values. The configuration defaults through `SHORTENER_PUBLIC_BASE_URL` to `http://127.0.0.1:8000`.

### Input validation

`url` must be textual, nonblank and an absolute HTTP or HTTPS URI with a valid host and port. Scheme matching is case-insensitive. Credentials, malformed escapes, raw control characters and percent-encoded control characters are rejected. An explicit empty port or a port greater than 65535 is invalid. Validation makes no network request to the destination.

When creation admission succeeds, missing or invalid bodies, malformed JSON, invalid destinations and invalid expiry values return **400 Bad Request**:

```json
{"error":"Invalid creation request"}
```

### Optional expiry and the seven-day maximum

Omitting `expiresAt` or supplying JSON `null` creates a link without expiration. Seven days is the effective maximum for a supplied expiry, not an automatic lifetime.

A supplied expiry must be ISO-8601 text with UTC offset; `Z` and `+00:00` are accepted. Non-UTC offsets, missing offsets and non-string values are rejected. Relative to one captured service clock instant, expiry must be strictly in the future and no later than `min(shortener.max-expiry-days, 7)` days afterward. The upper boundary is inclusive.

`application.yml` defaults `shortener.max-expiry-days` through `SHORTENER_MAX_EXPIRY_DAYS` to 30, but `UrlService` caps the effective maximum at seven days. A smaller positive setting imposes a stricter maximum. Nonpositive settings fail startup. Invalid expiry is rejected before code allocation when admission succeeds.

## Follow a link

`GET /r/{code}` returns **302 Found** for an eligible link, with the stored destination in `Location`. Each successful redirect atomically increments `clickCount` once and updates `lastAccessedAt` using the captured evaluation instant.

An unknown code returns **404 Not Found**:

```json
{"error":"Unknown code"}
```

An expiry equal to or earlier than the captured evaluation instant returns **410 Gone**:

```json
{"error":"Expired code"}
```

These 404 and 410 responses have no `Location` header. Expired redirects do not increment the counter or update the last-access timestamp. Non-expiring links remain eligible. HTTP verification must disable redirect following to observe the 302 response and its `Location`.

## Read analytics

`GET /api/urls/{code}/analytics` returns **200 OK** with `code`, `url`, `createdAt`, `clickCount`, `lastAccessedAt` and `expiresAt`. `lastAccessedAt` is null before any successful redirect; `expiresAt` is explicitly null for non-expiring links.

Analytics remains readable after expiration and does not increment counters or update access timestamps. An unknown code returns 404 with `{"error":"Unknown code"}`.

## Shared creation allowance

`shortener.creation-limit-per-minute` defaults through `SHORTENER_CREATION_LIMIT` to **20** and supports positive integer overrides. Invalid configuration fails startup.

One shared, process-local limiter covers creation attempts handled by this service instance. It does not allocate separate allowances by address, client headers or cookies. A fixed 60-second window measured with monotonic time starts on the first admitted attempt. The first configured number of attempts are admitted; a new window becomes available at exactly 60 seconds when another attempt arrives.

Admission occurs before request-body conversion and validation. Admitted malformed JSON, invalid destinations, invalid expiry and failed creations consume allowance. Internal code-collision retries do not consume additional slots.

Excess attempts return **429 Too Many Requests** with no `Location` header and this body:

```json
{"error":"Creation limit exceeded"}
```

`Retry-After` is an integer number of seconds: the remaining window duration rounded upward, with a minimum of one. Rejections do not extend the window and perform no code allocation or repository writes. Once exhausted, a request can receive 429 before its body would otherwise produce 400.

Redirects and analytics neither consume this allowance nor receive limiter responses. State resets when the process restarts; multiple instances have independent allowances. Fixed windows can admit up to twice the configured allowance across a window boundary.

## Other existing errors

Code allocation exhaustion returns **503 Service Unavailable** with `{"error":"Code allocation unavailable"}`. Unexpected failures handled by `UrlErrors` return **500 Internal Server Error** with `{"error":"Internal server error"}`.

## Source references

Paths below are relative to `backend/`:

- `src/main/java/com/urlshortner/urls/UrlController.java`: endpoint mappings, request parsing, response fields and configured public URLs.
- `src/main/java/com/urlshortner/urls/UrlErrors.java`: status codes, error bodies and `Retry-After`.
- `src/main/java/com/urlshortner/urls/Destination.java` and `ValidDestination.java`: destination validation and required textual input.
- `src/main/java/com/urlshortner/urls/UrlService.java`: expiry limits, redirect eligibility and analytics behavior.
- `src/main/java/com/urlshortner/urls/UrlRepository.java`: schema-qualified storage, exact expiry reconstruction and atomic redirect accounting.
- `src/main/java/com/urlshortner/urls/CreationLimitConfiguration.java` and `CreationRateLimiter.java`: admission timing, shared allowance and window calculation.
- `src/main/resources/application.yml`: public URL, expiry and creation-limit configuration defaults.

## Verification status

This page was checked against the supplied source and configuration. No current trusted-runner execution results were supplied.

Automated tests: Java tests, Python tests and frontend typecheck/build were not executed by this implementation stage.

Live runs: PostgreSQL verification and independent HTTP regression checks were not executed by this implementation stage. Existing Java and independent HTTP checks must pass through the trusted runner before regression acceptance is established. Historical results in other documentation do not establish results for this revision.
