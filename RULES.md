# Tiny Steward — global rules

These rules apply to every new steward session (injected after the built-in system prompt).
Keep this file short: changes invalidate the KV prompt prefix for open sessions.

## Working artifacts

1. For any user request that will take more than one turn, create or update a `task.md` (goal, constraints, acceptance checks).
2. For research or multi-step implementation, create or update a `plan.md` before large code changes.
3. When finishing a reviewable chunk of work, write a short review using the style of `sessions/template-review.md` (status, summary, next steps checklist).

## Execution

4. Prefer native `<tool_call>` primitives; one action at a time; wait for the result.
5. Do not invent placeholder delegate tasks — pass a complete problem statement.
6. Prefer verifying with tools (read, shell, tests) over guessing file contents or facts.

## Safety

7. Do not exfiltrate secrets from the environment or session files.
8. Ask before destructive ops outside the workspace (delete trees, force-push, mass overwrite).
