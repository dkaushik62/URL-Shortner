# Interview walkthrough

1. **Product first:** open URL Shortener. Create a link to `https://example.com/`, follow
   it and refresh analytics. Explain the Java API and persistence boundary.
2. **Greenfield evidence:** inspect the saved greenfield run. Show the starter lacking
   business logic, normalized requirements, decomposition, overlapping design/test branches,
   actual source diff and independent validation. Explain which calls used live Codex.
3. **Brownfield live or recorded:** request expiry. Show affected modules, additive migration,
   pre-change decision, real fault exercise/failure, bounded repair, passing checks and release
   decision. Scripted verification decisions are labelled; an interviewer can use the UI.
4. **Dynamic change:** revise 30 days to 7 days at a checkpoint. Show the old revision/approval,
   invalidation event, fresh plan, revised validation and a newly bound decision.
5. **Ambiguous request:** submit "make the service reliable at scale." Observe clarification
   before implementation; choose concrete creation limits and inspect the resulting `429`
   and `Retry-After` behavior. State the single-instance limitation.
6. **Governance:** reject an action or stop a run. Inspect rollback, receipts, preserved evidence
   and the missing promotion. Show restart recovery and bounded infrastructure retry.
7. **Defend decisions:** architecture, protected checks, no model secrets in generated-code
   environments, no cloud billing, measured metrics, and gaps needed for a production service.

Model generation is variable and subject to the operator's included usage. Keep the
recorded evidence available when a live run is slow or unavailable. Never present saved
evidence as a newly executing run or test-double results as real service validation.
