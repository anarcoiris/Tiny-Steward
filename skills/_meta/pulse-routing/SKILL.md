---
name: pulse-routing
description: "Lab spawn router for main: planner, coder, KB, atomic-exec only."
metadata:
  {
    "openclaw": {
      "emoji": "🧭",
      "requires": { "config": ["agents.list"] }
    }
  }
---

# Pulse routing (lab / main only)

Apply only when agent id is **main**. No skills fleet, no WhatsApp.

## Hard rules

- Every `sessions_spawn` must include `agentId` from the map below.
- Main does **not** run `exec` or `memory_search` — delegate to `atomic-exec` / `memory-search-ext`.
- Always `sessions_yield` after spawn accepted.
- Before planner/coder spawn: run [`delegation-gate`](../delegation-gate/SKILL.md) (auto or interactive).
- Cross-agent spawns: **`context: "isolated"`** (never `fork`).
- After spawn accepted, **next tool call MUST be `sessions_yield`** — no assistant text to user before yield.

## lightContext policy

| Target | lightContext | Notes |
|--------|--------------|-------|
| memory-search-ext, atomic-exec | `true` | Include absolute paths in task |
| planner (plan write) | `false` | Needs template + doc refs in bootstrap |
| coder (execute step) | `true` | Task **must** include `plan_path` + optional `skill_path` |
| skills-offensive, pentest | `true` | Interactive gate required |

## On wake (seeing child output)

Child results appear as a user turn with `[Internal task completion event]` and `Child result:`.

- After **planner**: `read` `metadata.plan_path` from Child result before spawning coder.
- Summarize for user. Fallback: `sessions_history` on child `session_key`.

## Pre-spawn checks

1. `read` `/home/openclaw/.openclaw/workspace/memory/delegation-gate-state.json`.
2. If `pending.<slug>.status` is `awaiting_user` — do **not** spawn; wait for user or `/approve`.
3. `session_status` — no duplicate in-flight child for same mission.

## Spawn map (lab)

| Need | agentId | Gate? | lightContext |
|------|---------|-------|--------------|
| Plan / evaluate / intake | `planner` | Yes | `false` |
| Execute / shell / edits | `coder` or `atomic-exec` | Gate for `coder` | `true` |
| KB / playbooks / config read | `memory-search-ext` | No | `true` |
| Bounded shell one-shot | `atomic-exec` | No | `true` |
| Offensive / red-team cluster | `skills-offensive` | **Interactive only** | `true` |
| Pen-test / fileless skill exec | `skills-penetration-testing` | **Interactive only** | `true` |
| Gateway config / maxDepth | `memory-search-ext` | No | `true` |

## Spawn task injection

Include in `task` when relevant:

```
plan_path: /home/openclaw/.openclaw/workspace/plans/<slug>.md
skill_path: /home/openclaw/.openclaw/workspace/skills/<folder>/SKILL.md
```

### Planner spawn example

```
sessions_spawn {
  agentId: "planner",
  lightContext: false,
  taskName: "plan_<slug>",
  task: "Write plan to workspace/plans/<slug>.md using _TEMPLATE.md. Topics: <user intent>"
}
sessions_yield
```

### Coder spawn example (after planner)

```
sessions_spawn {
  agentId: "coder",
  lightContext: true,
  taskName: "exec_S1",
  task: "Read plan_path: /home/openclaw/.openclaw/workspace/plans/<slug>.md. Execute step S1. Write deliverables to workspace/knowledge/. skill_path: (optional)"
}
sessions_yield
```

### Atomic-exec with skill

```
sessions_spawn {
  agentId: "atomic-exec",
  lightContext: true,
  taskName: "exec_<slug>",
  task: "skill_path: /home/openclaw/.openclaw/workspace/skills/<folder>/SKILL.md. Run bounded shell: <command>"
}
sessions_yield
```

## Two-phase offensive routing

1. Spawn `memory-search-ext` (no gate).
2. Interactive gate — user must approve before `skills-offensive` or `skills-penetration-testing`.

Workspace map: `workspace/docs/agent-workspaces.md`
