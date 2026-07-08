---
name: delegation-gate
description: "Lab delegation gate: auto_lab main approval or interactive questionnaire before main spawns planner/coder."
metadata:
  {
    "openclaw": {
      "emoji": "🚦",
      "requires": { "config": ["agents.list"] }
    }
  }
---

# Delegation Gate (lab / main only)

Apply only when agent id is **main**. Do not apply on worker agents.

## Policy source

1. `read` `/home/openclaw/.openclaw/delegation-gate-policy.json`.
2. `read` `/home/openclaw/.openclaw/workspace/memory/delegation-gate-state.json` before any planner/coder spawn.

Default lab mode: **`gateMode: auto_lab`**.

## Hard rules (never skip)

Before `sessions_spawn` targeting `planner` or `coder`:

1. Classify the request.
2. Apply gate mode (auto or interactive).
3. **`write`** `/home/openclaw/.openclaw/workspace/memory/delegation-gate-state.json` in the same turn, **before** spawn.
4. Spawn with typed `agentId` (ADR-004).

`memory-search-ext` and `atomic-exec` spawns do **not** require gate approval unless stand-ins for planner/coder work.

## Auto path (`gateMode: auto_lab`)

When policy `gateMode` is `auto_lab` and user has not run `/gate interactive`:

1. Classify → `approved_mode` + target `agentId`.
2. If target is in `alwaysAskAgentIds` → **interactive**.
3. If signal matches `alwaysAskSignals` → **interactive**.
4. Else auto-approve with `approved_by: "main"`, then `sessions_spawn` → `sessions_yield`.

## Interactive path

When escalated: write `pending` entry, post questionnaire, wait for user `/approve`, then spawn.

## After approval

Follow spawn map in [`pulse-routing`](../pulse-routing/SKILL.md). Gate controls **when**; typed `agentId` controls **how**.
