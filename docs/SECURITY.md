# Security and cost boundaries

| Boundary | Enforcement |
|---|---|
| Inference vs host execution | Inference-only CLI flags, typed outputs, forbidden tool-event detection |
| Proposed files vs repository | Canonical relative paths, extension/directory allowlist, protected manifests/entrypoint/config, symlink/traversal/device-path rejection |
| Source vs test authority | Protected HTTP checks reside in a separate trusted image; the model cannot edit them |
| Generated code vs host | Docker source mount is read-only; compilation happens on an internal copy; no host credentials or Docker socket |
| Network access | Build network disabled; candidate/demo applications use internal networks; browser access uses a fixed trusted bridge |
| Business vs control data | Separate PostgreSQL containers/networks; URL role has business access only; generated code cannot connect to engineering PostgreSQL |
| Decision vs side effect | Approval interrupts, exact artifact/revision matching, promotion receipts |
| Browser vs control APIs | Loopback bind/Host checks, exact local Origin validation, HttpOnly SameSite cookie, CSRF header for mutations; fixed bridge rejects foreign origins and requires the trusted proxy marker |
| Kernel calls | Explicit reviewed Moby syscall policy, independent of daemon defaults; active kernel filter verified |
| API keys vs persistence | Masked input, server memory only, no browser storage/graph checkpoint/log/artifact/test environment |
| Subscription vs API billing | ChatGPT login checked, API env keys stripped from CLI, API adapters opt-in, no automatic provider fallback |

Provider adapters use `https://api.openai.com` and `https://api.anthropic.com` over
HTTPS with redirects and environment proxy injection disabled. Custom endpoints
are not supported. Provider errors expose status/reason categories, not raw response
bodies. Invalid request responses omit input values. Known keys and key-like tokens
are rejected/redacted before recorded artifacts; never place secrets in requirements.

All source content and model outputs remain untrusted data. A user requirement does
not authorize arbitrary host commands, changes to the orchestrator, installation of
dependencies, cloud deployment, token sharing, or destructive migrations.

The local database passwords are deliberately disposable defaults, not provider
credentials. They are safe only within the documented loopback/internal-network
prototype. Never expose these services to a LAN or publish this configuration as a
production system. Generated migrations cannot modify existing migrations or issue
destructive/privileged SQL.

The app has no multi-user identity system. The local session establishes a same-origin
operator context, not authenticated human identity. UI, CLI and scripted verification
decisions are distinguished in evidence. Hash chains and stored approvals are useful
traceability; they are not independently tamper-proof archives.

Docker isolation is defense in depth, not a proof against kernel vulnerabilities or
malicious dependency packages. Trusted dependency setup is online; subsequent model
build/test execution is offline. Strong production execution would need dedicated
workers, network enforcement, tenant identity, protected secrets, artifact signing,
independent audit storage and a reviewed release pipeline.

Before publishing test evidence, remove hostnames and local machine paths with
`scripts/sanitize_test_reports.py`; pytest's JUnit export hook performs this step
automatically for this repository's tests. Review screenshots and saved artifacts
as well. This metadata filter does not replace a credential scan. Use a GitHub
no-reply commit email for future commits when a personal address should remain
private; changing that setting does not remove email addresses from existing history.
