# Testing and evidence

Run `python scripts/verify.py` after setup. It invokes no model and no billed provider.

- Python tests exercise graph branches/joins, source-repair limits, stale approvals,
  clarification, re-planning, receipt reuse, single-run scheduling, workspace boundaries,
  CSRF/Origin controls, redaction, audit tampering and opt-in API transport.
- Timeout recovery tests verify the 15-minute default/30-minute cap, terminal node
  state, preserved approvals/call/time budgets, bounded retries and persisted
  activity events. A trusted parent/child process fixture verifies process-tree
  cleanup on the executing OS; it does not invoke a model.
- State-machine tests use explicitly named doubles. They validate orchestration logic,
  not successful AI generation or Java execution. Application code never uses those doubles.
- The Docker runner compiles the actual Java candidate and executes its JUnit suite.
  Results include exit code, suite counts, failed assertions and logs. At least one
  executed JUnit case is required; empty/stale reports cannot establish success.
- A separately built trusted client checks the candidate's real APIs against a disposable
  PostgreSQL database: creation, redirects, exact destination, concurrent counting, URL
  validation, expiry and rate limiting as applicable. It cannot be edited by an agent.
- Frontend build includes TypeScript checking. Browser checks exercise connected state,
  user controls, short-link behavior, history, reload and responsive layout.

Immutable attempt directories retain jars and XML results. Source fingerprints and jar
hashes bind passing evidence to promotion. Runtime workspaces and databases are excluded
from Git. The published verification report distinguishes measured live runs, test doubles,
scripted decisions, provider coverage and any checks not performed.

Scenario source SHAs refer to their disposable Git repositories, not the monorepo's
delivery commit. Each export identifies its requirement revision, source SHA, validation
attempts, event chain, decisions and limitations. Saved exports are historical evidence,
not a newly executing graph or a substitute for the evaluator's own model access.

Success rate uses successful runs divided by all final terminal runs, including operator
stops/rejections. Active time excludes time spent paused at decisions; end-to-end latency
includes it. Recovery time is wall time from first failed validation to green validation
and includes any intervening waits. Absence of a recovery sample is "not available".

Physical macOS/Linux setup and provider account entitlement cannot be established by
Windows automated tests. Production scale, multi-user authorization, external audit
integrity and cloud deployment are outside this local verification.
