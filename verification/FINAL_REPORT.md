# Final submission verification - 15 October 2026

The submitted application includes the merged error/exception/logging enhancement from PR #5. The six real executions are preserved in [live-runs](live-runs/) and the [checksum manifest](manifest.json). Five succeeded and one stopped safely. No new Workbench model calls, paid-provider calls or cloud deployment were needed to prepare this submission pack.

## Final checks

| Check | Result / proof |
|---|---|
| Assignment coverage | All seven sections, eight core requirements and orchestration subrequirements mapped in [short answers](../docs/ASSIGNMENT_ANSWERS.md). Original three-page PDF was visually reviewed; its identity hash is recorded there. |
| Python governance/security | 75 passed, 1 skipped. [JUnit receipt](final-python-junit.xml). The Windows symlink fixture requires privileges unavailable in this session; other path/traversal protections passed. |
| Frontend | TypeScript and Vite production build executed successfully in pinned Node 24 Docker tooling, with the build stage cache disabled. [Build receipt](final-frontend-build.txt). |
| Final Java candidate | 107 JUnit tests passed in the isolated runner. Includes seven new error/logging tests plus existing validation, collision, expiry, rate and concurrency tests. [Receipt](final-service.json). |
| Independent HTTP checks | 39 passed: 18 against a fresh database and 21 against populated V1. Real PostgreSQL, creation, redirect headers, concurrent click accounting, input rejection, expiry/410, rate/429/Retry-After and upgrade preservation. [Receipt](final-service.json). |
| Current execution isolation | All 14 checks passed: non-root/read-only/resource-bounded application, explicit active syscall filter, no host auth/socket, isolated engineering database and blocked outbound access. [Receipt](final-isolation.json). |
| Six actual archives | All six file checksums and event chains valid; earlier five files preserved byte-for-byte. [Run/metrics index](final-run-summary.json), [manifest](manifest.json). |
| Browser and business APIs | Connected six-run history, archived artifacts, latest test results, real URL creation/redirect/analytics, error envelope and compact layout checked. [Receipt](final-browser-api.json), [screenshots](SCREENSHOTS.md). |
| Clean checkout without model access | A clean clone and separate virtual environment/engineering database inspected all six archives and business APIs with no Codex in the server PATH. No account tokens were copied. [Receipt](final-fresh-checkout.json). Existing Docker download caches and the running business demo were used. |
| Repository delivery | Private repository; PRs #1-5 merged. Documentation-only PR #2 and logging PR #5 were created by the governed workflow. [GitHub receipts](final-github.json). |
| Submission portability/integrity | Standard-library [submission verifier](../scripts/verify_submission.py) checks all six runs, 69 attached files and local document links. Deliberately corrupted archive/chain/proof fixtures are rejected. [Proof manifest](submission-manifest.json), [integrity receipt](submission-integrity.json). |

These are measured checks of the final submitted code/evidence. State-machine and optional-provider tests use labelled doubles; they do not count as live agent runs. Historical runs retain the controls and evidence available when they executed, as described in the earlier reports.

## Six real executions

The final columns describe each run's last validation, not a sum across repair attempts. The stopped run's missing acceptance result is unavailable, not a pass.

| Scenario / record | Result | Java / HTTP | Calls | Active time | Wall latency |
|---|---|---|---|---|---|
| [Greenfield failed attempt](live-runs/greenfield-cef8b2f4cbd741be838fc8d6f42f6218.json) | Safely stopped after source failures/incomplete trusted cache | No passing validation | 13 | 10m 15s | 10m 14s |
| [Greenfield accepted](live-runs/greenfield-fcc92f3051df4ef19b8dfc875295e94e.json) | Succeeded after two source repairs and one infrastructure retry | 65 / 10 | 13 | 14m 17s | 30m 59s |
| [Brownfield expiry](live-runs/brownfield-9915f2f65342408082cafb6012145005.json) | Succeeded; labelled fault repair and 30-to-7-day revision | 92 / 15 | 19 | 22m 24s | 32m 59s |
| [Ambiguous scaling](live-runs/ambiguous-88daf6c969d441c79b2f852abb2ec94a.json) | Succeeded after clarification, fixture repair and restart recovery | 100 / 13 | 10 | 11m 25s | 17m 46s |
| [Documentation enhancement](live-runs/enhancement-aeddd134cf2d44d59db0fa37436686f6.json) | Succeeded; PR #2, checkpoint restart/reconciliation, no local promotion | 100 / 39 | 7 | 6m 47s | 12m 32s |
| [Error/exception/logging enhancement](live-runs/enhancement-9ed4825c0fbe47acafdd6a1cb5559c35.json) | Succeeded; timeout recovery, compile repair, PR #5 and approved local promotion | 107 / 39 | 11 | 17m 35s | 71m 11s |

Active and wall timestamps are separate measurements; the stopped legacy run's accounting includes shutdown time and differs slightly from its terminal timestamps. Its original evidence is retained rather than rewritten.

## Reliability metrics and definitions

This is a six-run demonstration sample, not a production reliability estimate. [The snapshot](final-run-summary.json) includes exact values and per-run timing.

- **Success:** 5 / 6 terminal runs = 83.33%. Stops and unsuccessful runs stay in the denominator.
- **Retries:** 6 recorded model/explicit checkpoint retries, including the timeout retry. Source repairs are separate events and are not added again.
- **Rollback:** 7 recorded checkpoint rollbacks across six runs; 1.17 events per run. This is not a business-data deletion count.
- **Recovery / MTTR proxy:** 660.994 seconds (11m 1s), averaged over four runs with a recorded first failed validation followed by passing validation. Operator/recovery waits can be included. A model timeout alone does not start this validation-recovery clock. Runs without a recovery sample are unavailable, not zero.
- **End-to-end latency:** creation-to-completion wall duration, including approval and recovery waits. Mean across all six terminal runs: 1756.974 seconds (29m 17s). Per-run values are above; the latest run took 71m 11s wall time but only 17m 35s active execution, including its earlier timed-out attempt.
- **Active execution:** worker-accounted time retained across repairs/retries/revisions. Approval/clarification waits pause it. The default 30-minute ceiling is a bounded-demo policy, not a guarantee of completing arbitrary repository-wide work.

## What is proven and what remains limited

The greenfield, brownfield and ambiguous examples each include requirement/plan artifacts, dependencies, actual source diffs and measured validation. The brownfield export includes the reversible redirect fault, failed tests, repair, requirement lineage and renewed approval. The ambiguous export contains the clarifying workload/limits answer and a release checkpoint that survived restart. The latest enhancement includes an actual compiler error and repair rather than fabricated failure output.

The logging tests exercise safe envelopes, HTTP status/header preservation, request/MDC cleanup, servlet fixtures, single failure ownership, severity selection and sensitive exception sentinels. Browser/API probes confirm real 400/404 envelopes and ordinary INFO/WARN events. The protected HTTP suite primarily validates URL/expiry/rate/upgrade behavior. It does not prove every live servlet error-dispatch/committed-response path, production log ingestion or live unexpected-500 handling; fixture/unit coverage is labelled separately.

The following are explicit prototype/verification limits:

1. **Local single-user governance:** same-origin session/CSRF is not enterprise identity. Decisions record their source and do not claim independently authenticated human identity.
2. **Audit trust:** hashes, versions, receipts and ordered events provide traceability and tamper detection relative to a stored head. The same administrator could rewrite the database/head; independent signed storage is not implemented. No regulatory compliance certification is claimed.
3. **Scale:** one worker process, one active/waiting run, at most two parallel graph branches and a shared in-memory creation limiter. No distributed load/availability SLA or production benchmark is claimed.
4. **Release/model scope:** runtime agents edit only Java source/tests/docs within the allowlist. Platform/dependency/security changes require reviewed platform work. Implementation uses one proposal-generating model call at a time; effort is low. These historical runs selected CLI default rather than pinning an exact model name, which was not recorded. Results can vary with subscription/model availability.
5. **Provider/platform coverage:** default ChatGPT-authenticated Codex runs were real. OpenAI/Claude transport/security tests passed with doubles; their live billed APIs were not called. Setup/control scripts are cross-platform, but final execution was on Windows; Linux/macOS and physical phones were not executed.
6. **Deployment:** no cloud resources are provisioned. Production needs identity, independent audit/secret management, distributed scheduling/rate limiting, worker isolation hardening, signed artifacts, observability and an approved deployment pipeline.
7. **Rollback:** application/source rollback retains audit history and previous demo/database revisions; additive database columns may remain. Destructive downgrade migrations are not automatic.

Generated documentation was corrected after completed verification; the original model outputs and older five run exports were not edited to suggest those corrections existed during earlier execution. See [build stages](../docs/BUILD_JOURNAL.md) and [the submission route](../docs/SUBMISSION.md).
