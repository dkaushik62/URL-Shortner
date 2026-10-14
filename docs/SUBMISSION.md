# Submission entry point

This private repository contains the runnable prototype and the evidence for six real agent executions: five succeeded and one stopped safely. The failed run is deliberately retained.

## Reviewer route

1. Read [short answers to every assignment section](ASSIGNMENT_ANSWERS.md).
2. Follow [README installation and startup](../README.md). The submitted app, tests and evidence work without a model login; new live runs require the reviewer's own access.
3. Review [architecture](ARCHITECTURE.md), [orchestration](ORCHESTRATION.md), [decisions](DECISIONS.md) and [build stages](BUILD_JOURNAL.md).
4. Read [the final report](../verification/FINAL_REPORT.md), then inspect **Run History → Recorded demonstration evidence**. A fresh installation has an empty live history and six read-only archives.
5. Open the [proof/screenshot index](../verification/SCREENSHOTS.md) and [full run exports](../verification/live-runs/). Their [manifest](../verification/manifest.json) binds filenames to SHA-256 hashes.
6. Use [the interview walkthrough](DEMO.md) for the greenfield, brownfield/revision, ambiguous and current-project enhancement demonstrations.

## What is included

- Java URL creation, redirects, analytics, seven-day expiry, configurable shared creation rate limiting, centralized error codes and safe request-correlated logging.
- Stateful Python/LangGraph SDLC orchestration, checkpoints, two-branch joins, clarification, approvals, repair, rollback, revision and operation reconciliation.
- Connected React Workbench, URL Shortener and Run History; no fabricated run results.
- Real PR delivery evidence, final test receipts, isolation results, setup/recovery instructions and screenshots.

Verify archived evidence and attached proof checksums with `python scripts/verify_submission.py`. Verify application behavior with `python scripts/verify.py`; neither command invokes a model or enables billing.

The owner must grant the evaluator access to the private repository before submitting its URL. Local-only operation, Windows-executed verification, provider/model variability and production gaps are disclosed in the final report.
