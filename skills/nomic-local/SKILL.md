---
name: nomic-local
description: "Local Nomic/embeddings setup for this gateway: ollama-nomic :11438, memorySearch, KB paths."
metadata:
  {
    "openclaw": {
      "emoji": "🧬",
      "requires": { "config": ["agents.defaults.memorySearch.enabled"] }
    }
  }
---

# Nomic local (gateway)

Read `/home/openclaw/.openclaw/workspace/docs/nomic-local.md` for full setup.

Quick facts:
- Provider: `ollama-nomic` @ `http://172.22.48.1:11438`
- Model: `nomic-embed-text`
- Plugin: `memory-core`
- Indexed paths: `workspace/docs`, `skills`, `plans`, `knowledge`
- Config: `/home/openclaw/.openclaw/openclaw.json` → `agents.defaults.memorySearch`

For test plans or architecture questions, router should spawn **planner** — not answer from this skill alone.

## Router workflow (test plan)

1. Optional: `read` `nomic-local.md` + `openclaw.json` (one pass each) — **do not write the plan**.
2. Run delegation-gate (`auto_lab` approves planner).
3. **`sessions_spawn` `agentId: "planner"`** with full task text and absolute output path.
4. **`sessions_yield`** — next tool call must be yield, not more reads.

Allowed `agentId` values for router spawn: `planner`, `coder`, `memory-search-ext`, `atomic-exec`, `skills-offensive`, `skills-penetration-testing`. Use `agents_list` if unsure.
