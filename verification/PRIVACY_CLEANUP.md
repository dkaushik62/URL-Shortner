# Public evidence privacy cleanup

15 October 2026. This is a metadata cleanup, not a new agent run.

The four previously published Python JUnit reports have had their machine hostname
and local checkout/user-profile paths removed. Their test identities, suite counts,
outcomes, timestamps and durations were compared with the original main-branch
reports and remain unchanged. Failure/skip reasons remain available with private
path prefixes replaced by labels.

Future pytest JUnit exports are sanitized after pytest writes the XML, including
when a test fails or is skipped. Regression checks cover Windows/macOS/Linux user
paths, escaped paths, path parameters, idempotence, malformed XML and a real nested
pytest execution containing a deliberate failure and skip. The nested failure is
a trusted negative fixture, not a live application failure or agent repair.

Fresh verification is recorded in [the cleanup checks](privacy-cleanup-checks.json),
[the current Python report](privacy-python-junit.xml) and
[the Java/HTTP results](privacy-service.json). Frontend typechecking and production
build were run with Node 24. Java tests and independent HTTP acceptance checks,
including expiry/rate limits and a V1 database upgrade, run through the trusted
Docker runner. Previously attached results remain historical evidence.

All six live-run archives and their event chains remain byte-for-byte unchanged.
The submission manifest was refreshed for the reviewed metadata/documentation
changes and new verification attachments, then checked with
`python scripts/verify_submission.py`.

GitHub reported secret scanning and push protection enabled, with zero secret
alerts returned at the cleanup snapshot. The local repository now uses the
owner's GitHub no-reply identity for future commits; other clones must configure
their own author email. Existing commit-email metadata and original report bytes
remain in Git history. No history rewrite, force-push, credential rotation or
repository visibility change was performed. The detailed private audit and raw
local working files remain ignored and are not included in the submission.

A fresh Gitleaks scan of the complete candidate tree detected only the existing
synthetic credential-rejection fixture in `orchestrator/tests/test_security.py:55`.
No real account credential was identified. The private audit/scanner files remain
local; no raw credential strings were added to this report.
