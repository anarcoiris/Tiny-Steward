---
name: delegate-router
description: "Thin spawn delegate for main: route plan/code/offensive to router; direct KB/shell one-shots."
metadata:
  {
    "openclaw": {
      "emoji": "🔀",
      "requires": { "config": ["agents.list"] }
    }
  }
---

# Delegate router (main only)

Apply only when agent id is **main**. Do not classify — pass full user intent to **router** for multi-step work.

## Decision table

| User intent | Action |
|-------------|--------|
| Conversational / clarify / summarize child result | Reply inline — **no spawn** |
| Plan, strategy, roadmap, evaluate, Nomic setup, test planning | spawn **router** |
| Code, files, edits, deliverables, KB corpus build | spawn **router** |
| Offensive / red-team / pentest | spawn **router** |
| Web research + organized KB (.md by topic) | spawn **router** |
| Quick KB / playbook / config lookup | spawn **memory-search-ext** directly |
| Single bounded shell command (`ls`, one exec) | spawn **atomic-exec** directly |

## Hard rules

- **Never** spawn `planner`, `coder`, `skills-offensive`, or `skills-penetration-testing` from main — use **router**.
- **Never** use `atomic-exec` for planning, roadmaps, or Nomic architecture — that is **router → planner**.
- Always `sessions_yield` after spawn accepted.
- Cross-agent spawns use default **`context: "isolated"`** — never `context: "fork"`.
- Pass full user intent in `task`; do not pre-classify.
- **`sessions_spawn` requires all fields:** `agentId`, `task`, `taskName`, `lightContext: true`. Never call with empty args.
- Config path: `/home/openclaw/.openclaw/openclaw.json` (not `config/deployment/`).
- Use `agents_list` if unsure which `agentId` values are allowed.
- **After spawn accepted, next tool call MUST be `sessions_yield`** — no assistant text to user before yield.

## On wake after yield

Child results arrive as a **user turn**, not in `subagents` output. Look for:

1. `[Internal task completion event]` with `Child result:` — summarize that block for the user.
2. Router passthrough (if you spawned router) — same `Child result` content from router's terminal message.

If the event is missing but `subagents` shows `done`, call **`sessions_history`** on the child's `session_key` from the event header or recent list; summarize the last assistant message.

**Never invent** child findings. If no result is available, say the child completed with no visible output and offer to re-run.

Do **not** spawn again unless the user asks a new question or handoff says `status: continue` with work for main.

## Spawn examples

Route to router:

```
sessions_spawn {
  agentId: "router",
  lightContext: true,
  taskName: "route_<slug>",
  task: "<full user request>"
}
sessions_yield
```

Direct KB lookup:

```
sessions_spawn {
  agentId: "memory-search-ext",
  lightContext: true,
  taskName: "kb_<slug>",
  task: "<lookup question; read /home/openclaw/.openclaw/openclaw.json for config keys>"
}
sessions_yield
```

Concurrent dual spawn (Nomic + maxDepth), then yield once:

```
sessions_spawn {
  agentId: "router",
  lightContext: true,
  taskName: "route_nomic_plan",
  task: "<full user request for planner / Nomic test plan>"
}
sessions_spawn {
  agentId: "memory-search-ext",
  lightContext: true,
  taskName: "kb_maxdepth",
  task: "Read /home/openclaw/.openclaw/openclaw.json; report maxSpawnDepth and maxConcurrent."
}
sessions_yield
```

Direct shell:

```
sessions_spawn {
  agentId: "atomic-exec",
  lightContext: true,
  taskName: "exec_<slug>",
  task: "<exact shell command to run via exec>"
}
sessions_yield
```
