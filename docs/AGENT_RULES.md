# Agent Rules

- Work only on local branch Moaz. Never push, never touch remotes, never force, rebase, reset --hard, delete branches, or rewrite history. Commit locally at the end of each phase with message "phase N: <summary>" and create a local tag phase-N-complete. Never commit secrets, .env, caches, or build output.
- Every phase begins by inspecting the real repository state (git status, tree, docs/PROGRESS.md, the previous phase's report) and verifying the previous phase's acceptance criteria by running its tests. If verification fails, stop and report. Do not build on a broken base.
- Do not rewrite or reformat working components from earlier phases. Make minimal, justified changes and list them in the report.
- Never modify files under data/raw. Provenance of original datasets must be preserved.
- No fake data, no fabricated scientific values, no hardcoded or canned LLM answers, no mocked responses outside the test suite, and no bypassing the retrieval pipeline. Test doubles live only under tests/.
- Every numeric result shown to a user must be computed by deterministic code from validated data, never by the LLM.
- Strong typing (mypy strict on src/flame), ruff clean, Pydantic v2 models at every boundary, no unused code, English-only comments and docs.
- Add only the dependencies the phase names. Any other dependency needs a written justification in the report.
- Secrets only via environment variables loaded by the config module. Never log secrets.
- Each phase leaves the project runnable and all tests green.
- Each phase ends with a report appended to docs/PROGRESS.md and printed in chat, with sections: what was done, files changed, tests run with results, acceptance criteria checked one by one, issues found, deviations from the prompt, remaining work.
