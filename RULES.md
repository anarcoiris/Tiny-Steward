# Tiny Steward — global rules

These rules apply to every new steward session (injected after the built-in system prompt).
Keep this file short: changes invalidate the KV prompt prefix for open sessions.

## MEMENTO (context budget)

Everything you can read and generate in a session is limited. Past a point, history is
compacted/summarized. Treat valuable results as scarce: write them to `task.md` /
`plan.md` / review notes instead of relying on chat memory alone. Anticipate short-,
mid-, and long-horizon attention. Prefer being succinct and effective. Use tools
(clock, python calc, scripts) when arithmetic or time comparisons are unreliable —
build your own helpers when needed. `RULES.md` and related home files are durable;
protect them and spend tokens carefully.

## Working artifacts

1. For any user request that will take more than one turn, create or update a `task.md`.
2. For research or multi-step implementation, create or update a `plan.md` first.
3. When finishing a reviewable chunk, write a short review (see `sessions/template-review.md`).
4. Long logs/transcripts: use `/attach <path>` or `@\"path\"` — never paste huge terminal dumps.

## Workspace

5. Home is the process cwd (Tiny Steward repo root). Prefer relative paths from that home.
6. Tool calls must use `<parameter=NAME>…</parameter>` (never bare `<path>` tags).

## Execution

7. Prefer native `<tool_call>` primitives; one action at a time; wait for the result.
8. Do not invent placeholder delegate tasks — pass a complete problem statement.
9. Prefer verifying with tools (read, shell, tests) over guessing.

## Safety

10. Do not exfiltrate secrets from the environment or session files.
11. Ask before destructive ops outside the workspace (delete trees, force-push, mass overwrite).
