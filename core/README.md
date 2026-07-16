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
4. Mid-generation abort (closing the HTTP stream to free a slot) is **not** used; mailbox drain happens between turns only.

See `ui.delegate_terminal` in `config.yaml` for Windows Terminal / tmux / in-process spawn modes.
