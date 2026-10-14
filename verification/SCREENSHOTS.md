# Screenshot and proof index

Screenshots are observations of actual persisted runs. Saved runs are read-only historical evidence; they are not replayed or seeded as live executions. Test receipts and full exports establish results beyond the visible screenshot.

| View | Screenshot | Supporting record |
|---|---|---|
| Six runs and measured reliability metrics | [Final history](screenshots/final/history-six-runs.jpg) | [Metrics/run index](final-run-summary.json) |
| Successful greenfield | [Greenfield](screenshots/final/greenfield-success.jpg) | [Full export](live-runs/greenfield-fcc92f3051df4ef19b8dfc875295e94e.json) |
| Safely stopped greenfield | [Failed attempt](screenshots/final/greenfield-stopped.jpg) | [Full export](live-runs/greenfield-cef8b2f4cbd741be838fc8d6f42f6218.json) |
| Brownfield expiry and revised requirement | [Brownfield](screenshots/final/brownfield-expiry.jpg) | [Revision/fault/approval lineage](live-runs/brownfield-9915f2f65342408082cafb6012145005.json) |
| Clarified scaling request | [Ambiguous](screenshots/final/ambiguous-rate-limit.jpg) | [Clarification and actual validation](live-runs/ambiguous-88daf6c969d441c79b2f852abb2ec94a.json) |
| Documentation enhancement and PR | [Documentation enhancement](screenshots/final/enhancement-documentation.jpg) | [Full export](live-runs/enhancement-aeddd134cf2d44d59db0fa37436686f6.json) |
| Error/exception/logging enhancement | [Completed enhancement](screenshots/final/enhancement-logging.jpg) | [Full export](live-runs/enhancement-9ed4825c0fbe47acafdd6a1cb5559c35.json), [PR #5](https://github.com/dkaushik62/URL-Shortner/pull/5) |
| Latest generated Java validation | [Test evidence](screenshots/final/logging-test-evidence.jpg) | 107 JUnit tests / 39 protected HTTP cases in the logging export |
| Business flow and click analytics | [URL service](screenshots/final/shortener-analytics.jpg) | [Browser/API receipt](final-browser-api.json) |
| Compact viewport | [Mobile history](screenshots/final/mobile-six-runs.jpg) | [Browser/API receipt](final-browser-api.json); device emulation, not a physical phone |
| Model timeout recovery | [Resumed call](screenshots/timeout-recovery-chrome.png) | [Timeout report](TIMEOUT_RECOVERY.md), complete timeout/repair events in the logging export |

Earlier screenshots under this directory remain historical observations. Final captures supplement them; they do not alter earlier run events or approvals. Fresh test, isolation and clean-checkout receipts are linked in [FINAL_REPORT.md](FINAL_REPORT.md).
