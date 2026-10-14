# Engineering decisions

1. **Keep Java/Python/React.** Java is the target product; Python/LangGraph implements
   the lifecycle; React observes it. This preserves the agreed architecture and makes
   the orchestrator reusable for another governed Java target.
2. **Local completion first.** No cloud resources are provisioned. Hosting is separate
   from demonstrating actual engineering execution and requires its own security design.
3. **Subscription login as default.** Existing Codex access avoids adding an API billing
   dependency. Access and usage remain subject to the operator's account limits. API
   providers are configurable, deliberate opt-ins, not automatic fallbacks.
4. **Proposal-only model calls.** A model returns source and decisions in a typed schema.
   Deterministic repository tools and isolated execution own all side effects and measured
   checks. Prompts supplement rather than replace these policies.
5. **A graph, not a chained checklist.** Explicit parallel joins, interrupts, repair loops,
   checkpoint recovery and requirement invalidation demonstrate non-linear stateful work.
6. **Independent acceptance.** Model-written JUnit tests are useful but cannot be the sole
   authority. A protected black-box client checks real HTTP behavior and PostgreSQL counting.
7. **Dedicated business database.** Generated code has no access to run/checkpoint/audit
   data. Local disposable defaults allow setup without obtaining cloud credentials.
8. **Fixed trusted bridge.** This Docker installation does not expose ports on an internal
   application network. A tiny fixed-destination proxy allows loopback browser access without
   giving generated code external egress; HTTP checks execute inside that network.
9. **Real failures stay visible.** Failed platform setup, source defects and exhausted repair
   budgets are retained. A labelled fault exercise alters actual source; no passing/failing
   output or approval identity is fabricated.
10. **Single-instance rate limiting.** The ambiguous scenario resolves to a bounded local
    capability. It does not claim distributed throughput, availability or production scale.
