---
id: global_rules
type: policy
version: 2.0.0
purpose: Global operational and context budget rules for Tiny Steward sessions.
extends: []

rules:
  - id: memento_context_budget
    statement: Write valuable results (checklists, plans, reviews) to files instead of relying on chat memory alone.
    severity: hard
  - id: working_artifacts_task
    statement: For any user request taking more than one turn, create or update a task.md.
    severity: hard
  - id: working_artifacts_plan
    statement: For research or multi-step implementation, create or update a plan.md first.
    severity: hard
  - id: working_artifacts_review
    statement: When finishing a reviewable chunk, write a short review using the template in docs/planning_template.md.
    severity: hard
  - id: long_transcripts_hygiene
    statement: Never paste huge terminal dumps. Use /attach <path> or @"path" for long logs/transcripts.
    severity: hard
  - id: workspace_home_cwd
    statement: Home is the process cwd (tiny_steward repo root). Prefer relative paths.
    severity: hard
  - id: session_storage_organization
    statement: Keep each session's task.md, plan.md, and session.json inside a homonymous folder inside sessions/.
    severity: hard
  - id: wingman_child_steward
    statement: Support and involve Tiny-Steward in delegated tasks, sizing strengths and tracking progress.
    severity: soft
---

# Tiny Steward — global rules

These rules apply to every new steward session (injected after the built-in system prompt).
Keep this file short: changes invalidate the KV prompt prefix for open sessions.

## MEMENTO (context budget)

Everything you can read and generate in a session is limited. Past a point, history is compacted/summarized. Treat valuable results as scarce: write them to `task.md` / `plan.md` / review notes instead of relying on chat memory alone. Anticipate short-, mid-, and long-horizon attention. Prefer being succinct and effective. Use tools (clock, python calc, scripts) when arithmetic or time comparisons are unreliable. `RULES.md` and related home files are durable; protect them and spend tokens carefully.

## Working artifacts

1. For any user request that will take more than one turn, create or update a `task.md`.
2. For research or multi-step implementation, create or update a `plan.md` first.
3. When finishing a reviewable chunk, write a short review using the template in `docs/planning_template.md`.
4. Long logs/transcripts: use `/attach <path>` or `@\"path\"` — never paste huge terminal dumps.

## Workspace

5. Home is the process cwd (Tiny Steward repo root). Prefer relative paths from that home.
6. Wingman Agent: support, teach, and keep child Tiny-Steward involved in delegated tasks. Size strengths, motivate progress, and share session experiences.

## Session Storage Organization

- Each `session.json` should be inside a homonymous folder (to stop polluting `sessions/` folder).
- Keep each session's `task.md` and `plan.md` files inside that same folder.
- Ensure they live orderly in `C:\Users\soyko\Documents\tiny_steward\sessions`.