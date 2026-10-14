# URL Shortner · Agentic Engineering Workbench

A local Java URL shortener and a governed Python engineering system that builds,
tests and evolves it. The React workbench observes the real workflow, exposes its
artifacts and pauses for decisions. Shortening a URL does **not** invoke an agent.

## Start here

Prerequisites: **Git, Python 3.12+, and Docker Desktop/Engine with Compose v2**.
Start Docker and allocate at least 4 GB RAM. Initial setup downloads public package
dependencies and container images. No Firebase, Vercel or cloud billing is required.
Java 21, Gradle 8.14.3 and Node 24 are supplied by Docker; host Java/Node are not
required for the application. Windows, macOS and Linux use the same Python scripts.

The repository is private. Reviewers need access from its owner before cloning:

```text
git clone https://github.com/dkaushik62/URL-Shortner.git
cd URL-Shortner
python scripts/bootstrap.py
python scripts/start.py
```

On macOS/Linux, use `python3` if `python` is unavailable. Open
**http://127.0.0.1:8000**. The Java API is also available through a local proxy at
http://127.0.0.1:8080 for reads; use the session-protected port 8000 for mutations.
Engineering PostgreSQL binds only to 127.0.0.1:55432. Business PostgreSQL is a
separate container on the internal network, with no published port. These fixed
ports and named containers support one local installation at a time.

The submitted URL service, UI, automated tests and bundled evidence work without
a model connection. **New live engineering runs need the operator's own model
access.** Your credentials and the author's account tokens are never distributed.

For the development stages, start with [the build journal](docs/BUILD_JOURNAL.md)
and the repository's commit history. The original implementation was merged
through PR #1, retaining its stage commits. PRs #2 and #3 added verified enhancement
evidence and the governed GitHub delivery workflow to the default branch.

The submitted service includes expiration capped at **7 days** and a shared local
creation limit of **20 requests/minute**, configurable with
`SHORTENER_CREATION_LIMIT`. Redirects and analytics remain unlimited. The saved
greenfield baseline has neither enhancement, so the brownfield exercise still
starts from the original service. See [scenario summaries](docs/SCENARIO_SUMMARIES.md)
and [verification evidence](verification/REPORT.md).

### Default live model connection: existing ChatGPT access

Install Codex CLI and sign in using **ChatGPT**, not an API key. A pinned official
CLI package is available with `npm install -g @openai/codex@0.162.1` if you already
have Node/npm; the Codex desktop installation may also supply the CLI. Then:

```text
codex login
codex login status
```

The default provider consumes your existing plan's included usage and remains
subject to its access/usage limits. The system never purchases credits, falls back
to an API key, or silently selects a billed provider. An exhausted account stops
the run. The development machine used Codex CLI 0.162.0-alpha.17.2.

[Codex automation](https://learn.chatgpt.com/docs/non-interactive-mode) supports
saved authentication and structured outputs; [authentication](https://learn.chatgpt.com/docs/auth)
distinguishes ChatGPT subscription access from API-key usage.

## Submit a new enhancement and get a GitHub PR

The default **Agent Workbench → Enhancement → Enhance current project** option
uses the existing Java service, including its expiry and rate limiter. Paste your
change and acceptance criteria into **Engineering requirement**, then click
**Execute requirement**. This mode changes the Java service and its tests/docs;
changes to the Python/React platform or dependencies require a separate reviewed change.

GitHub delivery also needs **GitHub CLI (`gh`)** installed and signed in:

```text
gh auth login
gh auth status
```

Use an account with write access to the private repository. The app reads its
destination from `origin`; model agents never receive GitHub credentials or tools.
The current Java source must match GitHub's default branch. Commit/review/merge
previous backend changes and update the checkout before starting another enhancement.
This prevents a new PR from silently including someone else's unfinished edits.

1. Review the proposed change and approve sandbox implementation when prompted.
2. Inspect **Source diff** and **Test evidence**. Real Java and independent HTTP
   checks verify the requested code plus existing URL/expiry/rate behavior and a V1 upgrade.
3. Click **Approve & create draft PR**. The app commits the validated changes to
   `workbench/<run-id>-r<revision>`, pushes it and creates a private **draft PR**.
4. The **Draft PR ready** panel links to the PR. It includes requirement, engineering
   decisions/review, documentation and test evidence in a committed JSON artifact.
5. Choose **Finish without local promotion** to keep the existing demo, or
   **Approve local promotion** to run the validated candidate locally. Neither
   choice merges the PR; review and merge it separately in GitHub.

Runs continue independently of the browser but pause for clarification and
approval. Transport failures retain a delivery journal; use the bounded retry
control to reconcile an already pushed branch/created PR. No force-push, automatic
merge, repository visibility change or new paid model fallback occurs.
See [enhancement delivery and recovery](docs/ENHANCEMENT_DELIVERY.md).

## Demonstrate the assignment

1. Open **URL Shortener**, paste an HTTP/HTTPS URL, create a link, follow it and
   refresh its analytics. The business service stores URLs without fetching them.
   Open **Run History → Recorded demonstration evidence** to inspect the author's
   actual runs without invoking a model; they are read-only and excluded from your
   installation's live metrics.
2. Open **Agent Workbench**, choose **Greenfield**, inspect the requirement and
   execute. Its starter has build configuration and the Spring entry point, but
   no URL creation, redirects, analytics or business migration.
3. Inspect parallel architecture/test-design branches, generated source diff,
   JUnit results and protected HTTP acceptance checks. Review and approve the
   exact validated release to promote it into the local demo.
4. Execute **Brownfield** against the saved greenfield baseline. It adds nullable
   expiration with an additive migration and a configurable maximum lifetime.
   Enable the labelled source-fault exercise to observe an actual incorrect
   redirect status, failed acceptance, bounded repair and re-validation.
5. At a checkpoint, change `30 days` to `7 days`. Old downstream artifacts and
   approvals are invalidated, their lineage remains visible, and the graph re-plans.
6. Execute **Ambiguous**. Clarify "make the service reliable at scale" into the
   supported local scope: configurable creation rate limiting, `429`, `Retry-After`,
   unlimited redirects and an explicit single-instance limitation.

Only one run may be active or waiting. Finish or stop it before another run.
New live brownfield runs require a newly promoted greenfield source/database pair
in this installation. Greenfield starts a fresh link collection; enhancements copy
the appropriate existing database, retaining the previous demo for rollback. See
[database promotion](docs/DATABASE_PROMOTION.md). Saved scenario evidence is
immediately readable and does not require a new greenfield run.
Parallel nodes can overlap inside that run. UI refresh/closure does not drive or
erase execution. Runs and LangGraph checkpoints persist in PostgreSQL; after a
worker restart, interrupted runs require **Resume**. Temporary API credentials
must be supplied again. Checkpoint retries preserve consumed budgets.

The optional command-line driver is intended for controlled demonstrations:

```text
# Windows
.venv\Scripts\python.exe scripts/live_demo.py greenfield
# macOS/Linux
.venv/bin/python scripts/live_demo.py greenfield
```

Without `--approve`, it waits for decisions in the UI. `--approve` supplies CLI
decisions; `--verification --approve` explicitly records scripted verification
decisions. They are **not represented as authenticated human identity**.
Other options: `--fault`, `--revise-seven-days`, `--run-id EXISTING_ID`.

## Runtime configuration and credentials

Choose the provider, model identifier and bounded run limits in the workbench.
Changes to an existing run apply only at a checkpoint and enter its journal.
The model response limit defaults to **15 minutes per call** and can be set between
30 seconds and 30 minutes under **Execution limits & fault exercise**. The separate
30-minute active-run budget includes earlier attempts; a longer call limit cannot
extend it. While a response is pending, the UI shows elapsed time and receives
persisted activity updates every 15 seconds. These report worker activity, not
provider token progress or a completion estimate.

A Codex response timeout stops safely. Use **Retry from the saved checkpoint**,
choose **Model response limit (minutes)** and click **Retry this run**. This retains
the approved plan and consumed budgets and retries the unfinished stage. At most
two explicit timeout retries are allowed; rejected approvals and exhausted budgets
remain stopped. A timeout or stop also terminates the owned Codex process tree.
Model keys belong only in the masked key field. Do not paste credentials into
requirements. There is no key storage in browser storage, run records, checkpoints,
generated artifacts or build/test environments.

OpenAI and Claude API adapters are **disabled by default**. To deliberately opt in,
start the workbench with `ALLOW_BILLED_PROVIDERS=true` in the terminal environment.
Users must provide a model and their own API key; their provider may bill them.
The adapters use fixed official endpoints, not user-supplied URLs. Transport/security
tests use explicit doubles; see the verification report for live-provider coverage.

No auth tokens or model secrets belong in `.env`. `.env.example` describes local
database settings; the startup script does not automatically load dotenv files.

## APIs

| Endpoint | Behavior |
|---|---|
| `POST /api/urls` | Body `{ "url": "https://example.com", "expiresAt": "optional ISO instant" }`; returns `201` with `code`, `shortUrl`, `url`, `createdAt` |
| `GET /r/{code}` | `302` and exact destination in `Location`; atomically records a successful redirect |
| `GET /api/urls/{code}/analytics` | URL metadata, `clickCount`, `lastAccessedAt`, and expiry when implemented |
| `/engineering/runs` | Create/list runs; create requires a local session and CSRF header |
| `/engineering/runs/{id}` | State, node outputs, pending decision, diff and audit integrity |
| `/engineering/runs/{id}/events` | Persisted SSE with event IDs and reconnect cursor |
| `/engineering/runs/{id}/approval` | Decision bound to revision, approval ID and artifact hash |
| `/engineering/runs/{id}/clarification` | Answer an unresolved requirement at its current revision |
| `/engineering/runs/{id}/requirements` | Revise a paused requirement and invalidate downstream work |
| `/engineering/runs/{id}/stop`, `/resume`, `/retry` | Safe-stop, restart recovery, bounded infrastructure/model-timeout retry |
| `/engineering/runs/{id}/artifacts/{stage}` | Download a recorded artifact |
| `/engineering/metrics` | Success rate, retry/rollback totals and measured recovery time |

Business errors include `400` for invalid input, `404` for unknown links, `410` for
expired links and `429` for creation limits. Default max expiry is 30 days; the
demonstration can promote an explicitly configured seven-day revision.

## Verification, shutdown and reset

```text
python scripts/verify.py
python scripts/stop.py
```

Verification runs Python governance/security tests, frontend typecheck/build,
Java tests and independent HTTP checks against an isolated PostgreSQL database.
It does not invoke a model or enable billing. Stop the workbench terminal with
Ctrl+C. Container shutdown preserves the PostgreSQL volume.

For an intentional full reset of this assignment's database, stop the workbench
and run `docker compose down --volumes`. This deletes local links, run records and
checkpoints. `.runtime` also contains local workspaces/receipts; it is excluded from
Git. Saved evidence under `verification` remains separate historical evidence.

## Troubleshooting

- **Docker unavailable:** start Docker Desktop, wait for its engine, then rerun setup.
- **Port in use:** stop this assignment's previous installation or free 8000/8080/55432.
- **Codex unavailable/API login:** install the supported CLI, run `codex login`, and
  choose ChatGPT authentication. Existing API-key login is rejected in default mode.
- **Incomplete offline cache:** rerun bootstrap to rebuild the trusted runner, then
  retry the stopped infrastructure run. Agents cannot change dependencies to fix it.
- **Run stops:** inspect its recorded reason and test evidence. Source repair is
  bounded; rejected decisions and exhausted budgets cannot be bypassed with Resume.
- **Codex response timeout:** increase the response limit in the checkpoint retry
  panel. Completed planning and approvals remain recorded. The active-run budget
  still includes the timed-out attempt. See [timeout recovery evidence](verification/TIMEOUT_RECOVERY.md).
- **Java unavailable:** wait for its health check, inspect `docker compose logs backend`,
  or inspect the `urlshortner-demo` container after a promoted live run.
- **Native frontend tool errors:** use Docker bootstrap rather than an old host Node.
- **New checkout has no live history:** inspect the bundled verification evidence or
  run a new scenario with your own model access; there are no fabricated seeded runs.

Architecture, policies, trade-offs and the interview walkthrough are in `docs/`.
This is a local single-user prototype. Cloud deployment and production identity,
secret management, distributed scheduling and independently trusted audit storage
require a separate design and are not provisioned by this project.
