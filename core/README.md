# Tiny Steward — core package

Runtime, LLM clients, sessions, primitives, and mailbox for Tiny Steward.

## llama.cpp deployment checklist

Verified on the authoring host (2026-07-16):

| Lane | Port | Flags observed |
|------|------|----------------|
| orchestrator (qwythos) | 11440 | `--parallel 1`, `-c 262144` |
| atomic (qwen3-4b) | 11439 | `--parallel 1`, `-c 98304`, `--jinja` |

Implications:

1. With `--parallel 1`, concurrent out-of-process delegate children **serialize** on the atomic endpoint (503 "slot busy" is retried on stream and non-stream paths in `core/llm.py`).
2. `config.yaml` `llm.atomic.ctx: 98304` matches the atomic server `-c`; orchestrator server context is larger (`262144`) than the `98304` budget Tiny Steward uses for compaction — intentional headroom, not a bug.
3. Raise atomic `--parallel N` before relying on multiple simultaneous child terminals.
4. Mid-generation abort: during streaming, **Ctrl+C** closes the HTTP stream (best-effort free of the llama.cpp slot) and returns a partial response marked `[aborted]` without quitting the REPL.
5. Stats line shows **LCP** when the server emits `timings.cache_n` / `timings.prompt_n` (high `cache_n` ⇒ prompt prefix reuse).

See `ui.delegate_terminal` in `config.yaml` for Windows Terminal / tmux / in-process spawn modes.

## Reasoning / chat_template_kwargs (Qwythos)

Orchestrator defaults (`config.yaml`): `enable_thinking: true`, `preserve_thinking: false`, `thinking_budget_tokens: -1`, `cache_prompt: true`.  
Atomic defaults: thinking **off**, budget `0` (faster TTFT for micro-agents).

REPL:

- `/set enable_thinking on|off` — nested under `chat_template_kwargs` (alias: `/set thinking …`)
- `/set preserve_thinking on|off`
- `/set thinking_budget_tokens N` — sampler-side; safe to change mid-session
- `/set cache_prompt on|off` — keep `on` unless debugging LCP

Raw assistant text (including `<think>`) is stored in `session.json`; CoT is also mirrored to `sessions/<name>.think.jsonl`. Only the outbound LLM view strips think (unless `preserve_thinking`).

### KV-safe vs KV-breaking (client body)

| Param | Changes prompt tokens? | Safe to toggle mid-session? |
|-------|------------------------|-----------------------------|
| `temperature`, `top_p`, `repeat_penalty`, … | No | Yes |
| `thinking_budget_tokens` / `--reasoning-budget` | No | Yes |
| `max_tokens` | No | Yes |
| `cache_prompt: true` | Policy only | Keep stable `true` |
| `cache_prompt: false` | Forces recompute | Debug only |
| `chat_template_kwargs.*` (`enable_thinking`, `preserve_thinking`, …) | **Yes** | **No** — invalidates / shortens LCP |
| `tools` array in body | **Yes** | Prefer send-once (Tiny Steward policy) |
| Editing earlier messages / system prompt | **Yes** | Breaks prefix from divergence |

With `cache_prompt=true`, appending a new turn usually reuses a long common prefix (`cache_n` high). Toggling thinking kwargs mid-session warns in `/set`.

## Global RULES.md

- Config: `rules.enabled` / `rules.path` in `config.yaml` (default `./RULES.md`).
- Injected after the built-in system prompt on every conversation rebuild (`run_task`, REPL start, `/session` switch). Not stored inside `session.json` history.
- REPL: `/rules` (preview), `/rules reload` (re-read disk; may invalidate LCP).
- Keep the file short — it sits in the KV-sensitive system prefix.

## Retired modules

See [`plans/archivos-retirados.md`](../plans/archivos-retirados.md) for deletions such as `core/micro_agent.py` (absorbed into `Runtime` delegate paths).
