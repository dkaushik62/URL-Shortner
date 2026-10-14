# Engineering outcomes

The bundled [run exports](../verification/live-runs) contain actual Codex outputs,
source diffs, revision lineage, validation histories and ordered event chains.
Open them from Run History in a fresh installation; no model connection is needed.

## Greenfield

Run `fcc92f3051df4ef19b8dfc875295e94e` began with only trusted build/configuration
and the Spring entry point. The agent generated HTTP/HTTPS validation, secure code
allocation with bounded conflict retries, creation, redirects, atomic click
accounting, analytics, a Flyway migration and tests. Final validation executed
65 JUnit tests and 10 independent HTTP cases against isolated PostgreSQL.

Two source repairs fixed generated behavior/tests. An infrastructure retry followed
repair of the trusted runner's dependency/network setup. The release was promoted
locally after a scripted `verification` approval. The first unsuccessful greenfield
run `cef8b2f4cbd741be838fc8d6f42f6218` remains in the archive.

## Brownfield and changed requirements

Run `9915f2f65342408082cafb6012145005` began with the saved greenfield baseline.
It added nullable expiration through an additive V2 migration, injected Clock
tests, HTTP 410 for expired links and precise timestamp handling. Existing links
remain non-expiring. A clearly labelled filter fault changed redirects from 302
to 301; independent checks failed, and the agent repaired the actual source.
The repaired filter remains as a harmless pass-through with provenance in the diff.

Before release, the maximum changed from 30 to 7 days. Revision 1 outputs and
its release approval were invalidated, retained in lineage, and replaced by
revision 2. Replaying the old approval returned HTTP 409. Final validation ran
92 JUnit tests and 15 HTTP cases; a renewed approval preceded promotion. Three
infrastructure retries are retained, including CLI metadata compatibility fixes.

## Ambiguous reliability request

Run `88daf6c969d441c79b2f852abb2ec94a` was created through the browser. “Make the
service reliable at scale” paused before planning. The clarification narrowed
scope to a configurable shared local creation bucket with 20 attempts/minute,
HTTP 429 and Retry-After, unlimited redirects/analytics, and unchanged seven-day
expiration. All requests through the local bridge share the bucket. This is not a
distributed limiter, remote-client attribution system or production load benchmark.

Two generated HTTP fixture failures triggered one source repair. Final validation
ran 100 JUnit tests and 13 independent HTTP cases. A deliberate server restart at
the release gate retained the exact approval, source and call count; browser
refresh restored the gate. UI automation supplied the local approval, without a
claim of authenticated human identity. Promotion completed after a Docker timeout
and one infrastructure retry. The final verification also re-checks expiration
and a V1 database upgrade containing an existing row.

## Evidence limits

State-machine tests use named doubles; scenario records use real model/Docker
execution. Optional OpenAI/Claude adapters have transport/security tests only.
Their structured-output request contracts follow the official documentation:
[Claude structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
and [Codex CLI event types](https://github.com/openai/codex/blob/main/sdk/typescript/src/items.ts).
Local event hashes detect edits but are not independently signed or tamper-proof.
