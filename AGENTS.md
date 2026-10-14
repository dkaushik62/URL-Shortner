# Engineering boundaries

- Preserve the Java business service / Python control plane separation.
- Never execute model-generated code on the host. Use the trusted Docker runner.
- Runtime agents may edit only files allowed by `orchestrator/workspaces.py`; the
  orchestrator, runner configuration, dependency manifests and acceptance checks
  are protected. Dependency changes require an explicit reviewed platform change.
- Never commit provider credentials, account tokens, runtime databases, or raw provider logs.
  The documented disposable local database defaults are permitted for this prototype.
- Paid providers are opt-in. Never fall back from ChatGPT login to API billing.
- Report tests and live runs separately. Test doubles are not successful live runs.
- Before delivery run Python tests, frontend typecheck/build, Java tests and the
  independent HTTP acceptance checks; document anything not executed.
- Do not provision or deploy cloud services for this local assignment.
