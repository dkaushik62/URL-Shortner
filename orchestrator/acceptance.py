"""Protected black-box acceptance checks. Agents cannot edit this module."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import httpx


async def acceptance(base: str, scenario: str, max_days: int = 30, rate_limit: int = 20, check_legacy: bool = False) -> dict:
    cases = []

    def check(name, passed, details=""):
        cases.append({"name": name, "passed": bool(passed), "details": str(details)[:1000]})

    async with httpx.AsyncClient(base_url=base, timeout=10, follow_redirects=False, trust_env=False) as client:
        if check_legacy:
            legacy = await client.get("/api/urls/Legacy01/analytics")
            body = legacy.json() if legacy.status_code == 200 else {}
            check("V1 upgrade preserves historical row and clicks", legacy.status_code == 200 and body.get("clickCount") == 7 and body.get("url") == "https://example.com/legacy")
            check("V1 historical row remains non-expiring", body.get("expiresAt") is None)
            redirect = await client.get("/r/Legacy01")
            clicks = await client.get("/api/urls/Legacy01/analytics")
            check("V1 historical row redirects and increments after migration", redirect.status_code == 302 and clicks.status_code == 200 and clicks.json().get("clickCount") == 8)
        response = await client.post("/api/urls", json={"url": "https://example.com/engineering?from=acceptance"})
        check("create returns 201", response.status_code == 201, response.status_code)
        if response.status_code != 201:
            return {"passed": False, "cases": cases}
        body = response.json()
        code = body.get("code", "")
        check("creation includes short URL and random code", len(code) >= 6 and code.isalnum() and body.get("shortUrl", "").endswith("/r/" + code))
        redirect = await client.get("/r/" + code)
        check("302 redirect preserves destination", redirect.status_code == 302 and redirect.headers.get("location") == "https://example.com/engineering?from=acceptance", redirect.status_code)
        results = await asyncio.gather(*[client.get("/r/" + code) for _ in range(25)])
        analytics = await client.get(f"/api/urls/{code}/analytics")
        counts = analytics.json() if analytics.status_code == 200 else {}
        check("concurrent clicks are not lost", all(r.status_code == 302 for r in results) and counts.get("clickCount") == 26, counts.get("clickCount"))
        check("analytics includes timestamps", bool(counts.get("createdAt")) and bool(counts.get("lastAccessedAt")))
        unknown = await client.get("/r/noSuchCode9999")
        check("unknown link returns 404", unknown.status_code == 404, unknown.status_code)
        for label, url in [("invalid scheme", "javascript:alert(1)"), ("embedded credentials", "https://user:password@example.com"), ("control characters", "https://example.com/\r\nLocation:evil"), ("missing host", "https:///missing")]:
            bad = await client.post("/api/urls", json={"url": url})
            check(label + " rejected", bad.status_code == 400, bad.status_code)
        if scenario in {"brownfield", "enhancement"}:
            now = datetime.now(timezone.utc)
            invalid = await client.post("/api/urls", json={"url": "https://example.com", "expiresAt": (now + timedelta(days=max_days + 1)).isoformat()})
            check("expiry maximum enforced", invalid.status_code == 400, invalid.status_code)
            past = await client.post("/api/urls", json={"url": "https://example.com", "expiresAt": (now - timedelta(seconds=1)).isoformat()})
            check("past expiry rejected", past.status_code == 400, past.status_code)
            expiring = await client.post("/api/urls", json={"url": "https://example.com/expires", "expiresAt": (datetime.now(timezone.utc) + timedelta(seconds=2)).isoformat()})
            check("future expiry accepted", expiring.status_code == 201, expiring.status_code)
            if expiring.status_code == 201:
                expiry_code = expiring.json().get("code", "")
                await asyncio.sleep(2.2)
                expired = await client.get("/r/" + expiry_code)
                expiry_count = await client.get(f"/api/urls/{expiry_code}/analytics")
                check("expired link returns 410", expired.status_code == 410, expired.status_code)
                check("expired visits do not count", expiry_count.json().get("clickCount") == 0)
        if scenario in {"ambiguous", "enhancement"}:
            # All requests are from the same local client. Prior successful creation
            # counts; requests must eventually hit the configured limit.
            responses = [await client.post("/api/urls", json={"url": f"https://example.com/rate/{i}"}) for i in range(rate_limit + 2)]
            limited = [r for r in responses if r.status_code == 429]
            check("creation rate limiting produces 429", bool(limited))
            check("rate limit provides Retry-After", bool(limited) and bool(limited[0].headers.get("retry-after")))
            redirect = await client.get("/r/" + code)
            check("creation limits do not block redirects", redirect.status_code == 302)
    return {"passed": all(case["passed"] for case in cases), "cases": cases}
