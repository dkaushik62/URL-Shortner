# Short answers to the assignment

Reviewed against all three pages of the supplied **Interview Assignment: Build an Agentic Software Engineering System - URL Shortener** on 15 October 2026. The assignment is the evaluation source; repository policies and operator requests control execution. The original PDF is not republished. Its SHA-256 is `e6890463c402e67891cffdda9ffe2aef67880c43a1bd4a587657a62678411f42`.

## 1. Objective

The prototype turns a requirement into a plan, source changes, executed tests, a review, an engineering summary and an approved release or GitHub PR. A Python/LangGraph control plane coordinates the lifecycle; the React Workbench exposes its actual persisted state. See [architecture](ARCHITECTURE.md), [workflow](ORCHESTRATION.md) and [six actual executions](../verification/FINAL_REPORT.md).

## 2. Scenario

The Java URL service provides creation, redirects and click analytics backed by PostgreSQL. It was generated from an empty business starter, then enhanced with expiration, configurable creation limits, stable error codes, centralized exception handling and safe request-correlated logging. The [build journal](BUILD_JOURNAL.md) distinguishes stage commits from timestamped live agent execution; it does not invent a development chronology.

## 3. Scope

| Requested scope | Demonstration |
|---|---|
| Greenfield | Generated URL creation, redirects, analytics, schema, tests and documentation from the starter. |
| Brownfield | Added expiry to the accepted baseline; preserved existing links and revised the maximum from 30 to 7 days. A later enhancement added errors/logging across 13 source/test/documentation files. |
| Test/documentation improvement | Generated tests, protected HTTP acceptance, a documentation-only enhancement and its real GitHub PR. |
| Well-defined and ambiguous input | Clear API/expiry requirements and a scaling request that paused for clarification before implementing a shared local creation limiter. |

Each scenario's decomposition, artifacts, decisions and results are in [the saved runs](../verification/live-runs/) and [scenario summaries](SCENARIO_SUMMARIES.md).

## 4. Core requirements

| Requirement | Short answer and evidence |
|---|---|
| 1. Requirement understanding | The requirements stage normalizes intent and assumptions. Ambiguous scaling pauses for workload/limit clarification; its recorded answer explicitly narrows scope to one instance. [Ambiguous record](../verification/live-runs/ambiguous-88daf6c969d441c79b2f852abb2ec94a.json). |
| 2. Task decomposition | Schema-bound plans contain task IDs, dependencies and acceptance criteria. Invalid dependency graphs cannot pass the plan gate. [Engine](../orchestrator/engine.py), [governance tests](../orchestrator/tests/test_engine.py). |
| 3. Brownfield reasoning | Architecture and test-design stages inspect the current source and upstream decisions. Expiry touches APIs, service clocks, persistence and an additive migration; logging touches controller advice, request correlation and tests. [Brownfield record](../verification/live-runs/brownfield-9915f2f65342408082cafb6012145005.json), [logging record](../verification/live-runs/enhancement-9ed4825c0fbe47acafdd6a1cb5559c35.json). |
| 4. Workflow orchestration | Explicit graph nodes enforce entry/exit gates. Architecture/test design and validation/documentation run in parallel and join. Interrupts preserve approvals; failed validation loops through bounded repair. Checkpoints, context, versions and receipts persist in PostgreSQL. Requirement revision invalidates downstream outputs and stale approvals. [Control flow](ORCHESTRATION.md), [delivery flow](ENHANCEMENT_DELIVERY.md). |
| 5. Engineering output | Java source, SQL migrations, API/error documentation, JUnit tests, protected HTTP results and engineering summaries are reviewable artifacts. The latest generated service passed 107 Java tests and 39 independent HTTP checks. [Final evidence](../verification/FINAL_REPORT.md), [API/error catalogue](../backend/docs/http-behavior.md). |
| 6. Validation and risk control | The model cannot alter protected acceptance checks or platform configuration. Docker isolates generated execution. Tests cover input/collisions/counting/expiry/rate limits and governance/security failures. Failed runs remain visible. [Testing](TESTING.md), [security](SECURITY.md), [final receipts](../verification/FINAL_REPORT.md). |
| 7. Controlled autonomy | Agents propose allowlisted changes without host tools; the trusted orchestrator applies them. High-impact changes, PR publication and local promotion require revision-bound decisions. Users retain final review and GitHub merge control. [Engine](../orchestrator/engine.py), [PR evidence](../verification/enhancements/). |
| 8. Engineering summary | Each completed run retains plan/rationale, changes, tests, decisions and limitations. The submission adds a consolidated [final report](../verification/FINAL_REPORT.md), [decisions](DECISIONS.md) and [interview route](DEMO.md). |

### Detailed orchestration coverage

| Critical differentiator | Concrete control/proof |
|---|---|
| Non-linear graph, sequential/parallel paths and synchronization | LangGraph conditional edges, explicit multi-node joins and validation-to-implementation repair edge; graph shown in Workbench. |
| Cross-stage context and lineage | Agent inputs, source SHAs, revisioned artifacts, requirement history and ordered persisted events in every run export. |
| Approval checkpoints | Decisions bind approval ID, requirement revision and artifact hash. Brownfield's obsolete approval returned 409; rejection/changed-source tests block side effects. |
| Bounded retries and fallback | Three transient transport attempts, one schema-correction fallback on the same provider, two source repairs and bounded explicit checkpoint retries. No automatic paid-provider fallback. [Timeout recovery](../verification/TIMEOUT_RECOVERY.md). |
| Rollback and safe-stop | Restore validated source/baseline while retaining failed candidates and audit history. Receipts and delivery journals reconcile repeated operations. Stopped greenfield is retained as evidence. |
| Security, compliance and change control | Repository allowlist, protected migrations/manifests/checks, credential exclusion, isolated execution, loopback/Origin/session/CSRF controls. This demonstrates policy enforcement; it is not a regulatory compliance certification. |
| Observability and traceability | Persisted events, artifact/source hashes, decisions, source diffs, test receipts and SSE. Six checksum-verified exports have valid event chains. Local hashes are not independently trusted or tamper-proof audit storage. |
| Reliability metrics | Six runs: five successes, six retries, seven rollbacks; recovery and active/wall latency have explicit definitions and missing-sample handling. [Metrics](../verification/FINAL_REPORT.md). |
| Dynamic re-planning | The 30-to-7-day change preserves old lineage, rebuilds affected stages and requires a renewed approval. [Brownfield revision 2](../verification/live-runs/brownfield-9915f2f65342408082cafb6012145005.json). |

## 5. Deliverables

| Deliverable | Location |
|---|---|
| Runnable end-to-end prototype | [README setup/start/stop](../README.md), Java/Python/React source and locked build inputs. |
| Components, orchestration, control flow and decisions | [Architecture](ARCHITECTURE.md), [workflow](ORCHESTRATION.md), [decisions](DECISIONS.md), [PR flow](ENHANCEMENT_DELIVERY.md). Mermaid diagrams render in GitHub. |
| Three required scenarios | [Scenario summaries](SCENARIO_SUMMARIES.md), full saved JSON records and [screenshots](../verification/screenshots/final/). |
| Setup instructions | [README](../README.md): private access, prerequisites, authentication, cross-platform scripts, verification, troubleshooting and reset. |
| Testing, limitations and trade-offs | [Testing](TESTING.md), [security boundaries](SECURITY.md), [final verification](../verification/FINAL_REPORT.md). |

## 6. Evaluation criteria

| Criterion | Short answer |
|---|---|
| Agentic orchestration | Real model calls, persisted graph state, independent execution, interrupts, repair, revision and recovery demonstrate coordinated lifecycle work. |
| Architecture/system design | Java business behavior, Python governance and React observation are separate; business and engineering databases/networks are separate. |
| Decomposition/execution depth | Plans expose dependencies and acceptance gates; design/testing branch independently; downstream work consumes approved upstream context. |
| Output realism/quality | Six real runs include failures and repairs; generated Java compiles and runs against PostgreSQL. Source and validation are tied by hashes. |
| Validation/risk rigor | Independent HTTP checks supplement model-written unit tests; unsafe paths/actions and stale approvals are rejected. Live and simulated coverage are labelled. |
| Defensible decisions | [Decision log](DECISIONS.md) explains local-first operation, inference-only proposals, protected validation and single-instance scope. |
| Core engineering principles | Modular service/control-plane boundaries, deterministic concurrency/expiry tests, transactional click counting, validation, security controls and reviewed additive change. Distributed scaling remains future work. |
| Engineering judgment | Failures are retained, model claims do not establish test success, paid inference is opt-in, and production limitations are explicit. |

## 7. Expectation

The submission applies production-minded design and change controls to a runnable prototype. Humans own oversight, approval and final quality. It does not claim production deployment, enterprise identity, regulatory certification, independently trusted audit storage or distributed scale. These remaining production investments are stated in [the final report](../verification/FINAL_REPORT.md); they are not represented as completed capabilities.
