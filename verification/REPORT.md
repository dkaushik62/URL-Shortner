# Verification report

Evidence captured on Windows on 2026-10-14. No cloud deployment, billed provider,
or evaluator credentials were used. Run archives distinguish model output, executed
tests and scripted decisions. The private repository requires reviewer access.

| Check | Observed result |
|---|---|
| Python orchestration/security suite | 42 passed, 1 skipped. The symlink-file test was skipped because Windows did not grant symlink creation; path/traversal/case-alias policy checks passed. |
| Optional provider adapters | 11 transport/security tests passed after adding native structured output for Claude; no live OpenAI/Claude API call was made. |
| Frontend | TypeScript check and production build passed. |
| Final Java service | 100 JUnit tests passed. |
| Independent HTTP API/rate checks | 13 passed, including concurrent click counting, input rejection, 429, Retry-After and unlimited redirects. |
| Expiration plus populated V1 upgrade | 18 passed, preserving a legacy link and its clicks, non-expiring legacy behavior, seven-day cap, 410 and unchanged expired counts. |
| Docker isolation | 10 checks passed, including an external numeric-IP connection being blocked. See isolation.json. |
| Browser flow | Created a real ambiguous run, inspected/answered clarification, approved sandbox and release gates, inspected saved evidence, created a link, followed it and observed count 0 → 1. |
| Restart at release checkpoint | Exact approval, source SHA and model calls retained after server restart and browser refresh; recorded in the ambiguous run. |
| Obsolete approval | Replaying brownfield revision 1 approval against revision 2 returned HTTP 409. |
| Fresh checkout | Final verification is in progress; the receipt will be added after installation/startup checks. |

The first final HTTP verification attempt hit a Docker timeout while launching the
application. Its result is retained in `attempts/before-runtime-separation.json`.
The final checks reused that passing 100-test jar after separating the small runtime
image from the build image; both HTTP suites passed. The compose image also compiled
and ran the 100-test suite with external networking disabled.

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
