# Verification report

Evidence captured on Windows on 2026-10-14. No cloud deployment, billed provider,
or evaluator credentials were used. Run archives distinguish model output, executed
tests and scripted decisions. The private repository requires reviewer access.

| Check | Observed result |
|---|---|
| Python orchestration/security suite | 47 passed, 1 skipped; machine-readable python-junit.xml included. The symlink-file test was skipped because Windows did not grant symlink creation; path/traversal/case-alias policy checks passed. |
| Optional provider adapters | 11 transport/security tests passed after adding native structured output for Claude; no live OpenAI/Claude API call was made. |
| Frontend | TypeScript check and production build passed. |
| Final Java service | 100 JUnit tests passed. |
| Independent HTTP API/rate checks | 13 passed, including concurrent click counting, input rejection, 429, Retry-After and unlimited redirects. |
| Expiration plus populated V1 upgrade | 18 passed, preserving a legacy link and its clicks, non-expiring legacy behavior, seven-day cap, 410 and unchanged expired counts. |
| Docker isolation | 14 checks passed, including an active explicit kernel syscall filter, blocked external access and blocked connection to the separately networked engineering database. See isolation.json. |
| Browser flow | Created a real ambiguous run, inspected/answered clarification, approved sandbox and release gates, inspected saved evidence, created a link, followed it and observed count 0 → 1. |
| Restart at release checkpoint | Exact approval, source SHA and model calls retained after server restart and browser refresh; recorded in the ambiguous run. |
| Obsolete approval | Replaying brownfield revision 1 approval against revision 2 returned HTTP 409. |
| Fresh checkout | A clean local Git clone installed a new virtual environment, built the app and ran without Codex available in its server PATH. Four archives and their event chains remained inspectable; URL creation/redirect/analytics and preserved data passed. Existing Docker download caches and database volumes were retained. See fresh-checkout.json and fresh-checkout-service.json. |
| Database promotion rehearsal | Real fresh greenfield database, brownfield template copy preserving an existing link/clicks, and restoration of the prior demo passed using previously validated jars. This was model-free, not a new agent run. See database-promotion.json. |
| Mobile layout | Browser device emulation at 390 × 844: viewport and page width both 390, with no page overflow. Screenshot included; no physical-device claim. |

The first final HTTP verification attempt hit a Docker timeout while launching the
application. Its result is retained in `attempts/before-runtime-separation.json`.
The final checks reused that passing 100-test jar after separating the small runtime
image from the build image; both HTTP suites passed. The compose image also compiled
and ran the 100-test suite with external networking disabled.

Fresh setup also found a Gradle plugin-redirect TLS failure, a manifest-reference
mistake and startup/cleanup timing issues; the stage commits retain these fixes.
The pinned plugins now resolve directly from Maven Central with certificate checks
enabled. The trusted cache contains only the fixed manifests and starter entry point.

Historical live runs used the original shared PostgreSQL arrangement and daemon
syscall defaults. Final controls were then strengthened and tested separately:
engineering PostgreSQL is unreachable from generated code's internal network,
business databases are retained per promotion, and containers explicitly apply the
reviewed Moby syscall policy. Historical evidence has not been rewritten to claim
these controls were active during earlier runs.

## Live scenarios

Four real runs are included in [live-runs](live-runs): one unsuccessful greenfield,
one successful greenfield, successful revised brownfield, and successful clarified
ambiguous. SHA-256 export checksums are in [manifest.json](manifest.json). The app
recalculates event chains when reading saved evidence; it does not import them as
live work or inflate a new installation's metrics.

The snapshot success rate is 3/4 = 75%, including the unsuccessful run. Model and
infrastructure retries total 5; source-checkpoint rollbacks total 6. Mean recovery
is 807.227 seconds across the three recovered runs. These are demonstration samples,
not a reliability benchmark. Active duration counts execution segments; end-to-end
duration includes decision waits and recovery work. Detailed values are in each
run. Missing observations are “not available.”

Historical source SHAs belong to isolated workspace Git repositories. Newer runs
include captured agent inputs; early artifacts retain requirements, upstream outputs
and source references but do not include every complete prompt. No missing prompt
or tool event has been reconstructed and presented as original execution.

## Limits and deferred checks

- Workflow tests use explicitly labelled doubles; their passes are not live AI evidence.
- UI approvals during this verification were supplied by automation. The local
  workbench records their source and `authenticated_human_identity: false`.
- Hash chains and export checksums share the local administrator's trust boundary.
- The limiter has one shared local bucket and no distributed coordination or visitor
  identification. It enforces request attempts, including malformed creation input.
- Physical macOS/Linux setup, real mobile devices, provider account entitlements,
  optional live API adapters, production load/availability, and cloud deployment were
  not verified. Browser device emulation is documented separately from physical testing.
- Interrupted active-time accounting persists once per second; an abrupt process kill
  can lose the unobserved sub-second tail. Decision waits are excluded.

Re-run `python scripts/verify.py` after bootstrap without any model connection.
Run `python scripts/verify_isolation.py` while the demo is running. Historical
exports remain readable when Codex is absent or logged out.
