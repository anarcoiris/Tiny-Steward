# Tiny Steward — operator playbook

How to run sessions without wrecking LCP, how to attach long transcripts, and how
delegation terminals work.

## Workspace home

Steward’s home is the **process cwd** (usually the repo root:
`…/tiny_steward`). Prefer relative paths. Absolute Windows paths work for
primitives, but relative paths keep prompts and tools portable.

## Start a healthy session

1. Set thinking **in `config.yaml`**, not with a burst of `/set` at boot:
   - orchestrator: `enable_thinking: true`, `preserve_thinking: false`,
     `thinking_budget_tokens: -1` (or `8192`)
   - leave `cache_prompt: true`
2. `python steward.py --session <name>`
3. First user message = a concrete task (or `/attach` a transcript), **not** a
   paste of the previous REPL log.

## `/set` — what is safe

| Key | Mid-session? | Notes |
|-----|--------------|--------|
| `thinking_budget_tokens` | Yes | KV-safe |
| `temperature`, `top_p`, `repeat_penalty`, `max_tokens` | Yes | Sampling only |
| `enable_thinking`, `preserve_thinking` | **Avoid** | Changes prompt tokens → LCP cold |
| `cache_prompt` | Keep `true` | `false` only for debug |
| `model`, `base_url` | Rare | Rebuilds HTTP client |

Booleans accept only `on|true|yes|1` / `off|false|no|0`.  
`/set enable_thinking medium` is **rejected** (it used to silently become `false`).

See also: [`core/README.md`](../core/README.md) KV table.

## LCP (not “Language Context Protocol”)

Stats line: `LCP cache_n+prompt_n (pct%)`.

- High % → llama.cpp reused the prompt prefix (good).
- `0%` right after changing `chat_template_kwargs` / system / tools → expected
  for one turn; it should climb again if you stop toggling.

Steward does **not** split the KV cache across parallel inferences when the
server runs `--parallel 1`.

## Long transcripts — attach by path, don’t paste

| Method | Example |
|--------|---------|
| Meta command | `/attach sessions/inspect-and-supervise.json` |
| Inline ref | `Please review @"sessions/foo.jsonl"` |
| Agent tool | `read` / `ls` on the path |

Attachments are capped (`ATTACH_MAX_CHARS`). Prefer this over pasting terminal
dumps (paste confuses the model and destroys LCP).

Also: `@sessions/…`, `@plans/…`, `@core/…`, absolute paths, or quoted paths.

## Vision / images (F5)

**Host checklist (required before images work):**

1. mmproj GGUF on disk (e.g. `models/mmproj-Qwythos-…-F16.gguf` under the llamacpp tree).
2. Restart orch with vision: `.\start-qwythos-server.ps1 -WithVision` (args must include `--mmproj`).
3. Confirm `GET http://127.0.0.1:11440/v1/models` lists **multimodal** in `capabilities` (not only `completion`).
4. Optional once: OpenAI chat with a tiny PNG `image_url` data-URI returns a description.
5. Prefer a **new Steward session** after flipping `-WithVision` (KV-breaking vs text-only orch).

Config: `llm.orchestrator.vision: auto` (default) probes on startup; `on` requires multimodal; `off` refuses images. Atomic lane stays text-only (no mmproj).

| Method | Example |
|--------|---------|
| Meta | `/image path/to.png` |
| Attach | `/attach shot.jpg` (image suffixes → vision path) |
| Inline | `What is in @"sessions/.temp/shot.png"?` |

Session JSON stores **path + mime** refs (not multi-MB base64). Steward re-encodes to `data:image/…;base64,…` on the LLM call (size cap ~6 MB). Without mmproj, attach fails fast with a restart hint.

VRAM: projector adds ~0.9 GB. F8 browser ingest is deferred (not required for F5).

## Tool-call format (write)

Always:

```xml
<tool_call>
<function=write>
<parameter=path>
task.md
</parameter>
<parameter=content>
…
</parameter>
</function>
</tool_call>
```

Bare `<path>…</path>` is tolerated as a fallback, but teach
`<parameter=path>`. Skills under `_meta/primitives` use the native format.

If the model only emits `<think>` with no tool call, Steward nudges up to twice
before ending the turn.

## Delegation terminals (tmux / Windows Terminal)

Config: `ui.delegate_terminal` in `config.yaml`.

| Mode | Behavior |
|------|----------|
| `auto` | Windows: Windows Terminal split if `wt` exists, else new console. Unix + `$TMUX`: tmux split. Else in-process. |
| `windows_terminal` | `wt split-pane` child steward |
| `tmux` | `tmux split-window` (~25% height) |
| `console` | New console window (Windows) |
| `in_process` | Same process; `_run_delegate_loop` on atomic LLM |

Child entry: `steward.py --delegate-mode --parent … --delegate-skill … --problem …`  
Parent waits for mailbox `delegate_result` or session `status=done`.  
With atomic `--parallel 1`, concurrent children **serialize** (503 retries help).

`/tree` shows parent→children. `/mail <session> <text>` queues supervision.

## Prompt hygiene (do not paste the REPL)

Long messages that look like a terminal dump (box-drawing, `you ›`, `LCP`,
turn stats) are **blocked** at ingest. Use `/attach` or `@path` instead.

Outbound history also scrubs residual chrome and replaces think-only assistant
turns with `[thinking only — no reply text]` so the LLM never sees blank
assistant messages.

## Backend gate

`backends.gate` in `config.yaml` serializes client calls to orch / atomic /
embed (default 1 slot each). Interactive work outranks `/dream`. This does
**not** replace llama.cpp `--parallel N` (still F3 host side).

On startup (unless `--no-health-check`), Steward calls `GET /props` and warns
if `gate.*_slots` > server `total_slots`, or if yaml `ctx` > server `n_ctx`.
If yaml `ctx` < server `n_ctx`, that is intentional headroom (info only).

## F3 — `id_slot` and host `--parallel`

**Client (done):** `llm.orchestrator.id_slot: 0` pins orch requests to slot 0.
Atomic omits `id_slot` (server default `-1` = longest-prefix → LRU pick).

**Host (ops, still pending):** raise `--parallel N` only in
`~/Documents/Ollama/docker/llamacpp` launch scripts when you need concurrent
atomic children. Starting conditions before claiming F3 host done:

1. Atomic (and optionally orch) restarted with `--parallel N` (`N` ≥ children).
2. Set `--cache-ram` and `--cache-idle-slots` explicitly (do not rely on defaults).
3. Keep orch client pin (`id_slot: 0`); leave atomic at `-1` unless you intentionally pin children.
4. `GET /props` `total_slots` ≥ `backends.gate.*_slots` and ≥ intended concurrency.
5. Accept the LCP caveat: with `np>1`, prompt-cache checkpoints are **per slot** — a matching prefix on another slot still misses.

## F4 — slot save/restore (scope)

llama.cpp already recycles KV via longest-prefix / LRU and RAM prompt-cache.
Steward must **not** reimplement that.

| Layer | Meaning |
|-------|---------|
| Server RAM | prompt-cache + idle-slot recycle (always-on ops) |
| Server disk | `--slot-save-path` + `GET/POST /slots/{id}?action=save\|restore\|erase` — **host ops**, needs F3 multi-slot to be useful |
| Steward | Session JSON + `/tree` parent→children; `metadata.orch_id_slot` records the pin used |

**Restore a Steward chat** = `/session <name>` (reload messages) and rely on
server LCP / prompt-cache. Disk slot restore is optional host tooling, not a
Steward feature in this cycle.

## `/backend` launcher

`llm.*.launch` holds:

| Key | Role |
|-----|------|
| `cmd`, `cwd`, `autostart` | Process spawn (default `autostart: false`) |
| `parallel` | Appended as `-Parallel N` for PowerShell `start-*.ps1` |
| `profile`, `context` | Optional `-Profile` / `-Context` |
| `extra_args` | Free-form argv (use once host scripts accept `--cache-ram` etc.) |
| `cache_ram`, `cache_idle_slots`, `slot_save_path` | Annotations for ops; not sent unless in `extra_args` |
| `expect_total_slots` | After start, `GET /props` must match (defaults to `parallel`) |

REPL:

- `/backend start\|stop\|status <orch\|atomic>`
- `/backend props <orch\|atomic>` — live `n_ctx` / `total_slots` vs expect

F3 host raise: set `launch.parallel: N`, `expect_total_slots: N`, and
`backends.gate.atomic_slots: N` (or orch). Confirm with `/backend props atomic`.

F4 disk: annotate `slot_save_path` only — Steward does **not** call `/slots`.

## MCP paths

`mcp.python_exe` / `mcp.client_py` in `config.yaml` (fallback to historical
nina-mcp paths if omitted).

## Dreaming / memory

| Command | Effect |
|---------|--------|
| `/dream` | Consolidate new `*.think.jsonl` rows via atomic LLM → `*.memory.jsonl` + `*.memory.md` |
| `/dream <session>` | Same for another session |
| `/memory` | Show current `memory.md` and refresh the system “Integrated memories” block |

Watermark: `session.metadata.dream_watermark`. Compaction prefers `memory.md`
over raw truncated chat. Facts vs hypotheses stay separated in the template.

## Docs map

| File | Role |
|------|------|
| [`plans/fuera-de-alcance.md`](../plans/fuera-de-alcance.md) | Live backlog (F3+) |
| [`plans/archive/`](../plans/archive/) | Closed cycles |
| [`plans/archivos-retirados.md`](../plans/archivos-retirados.md) | Deleted modules (e.g. `micro_agent.py`) |
| [`RULES.md`](../RULES.md) | Global rules injected into system prompt |
| [`sessions/`](../sessions/) | **Local only** — not for git |

## Sessions must stay local

`sessions/*` is gitignored. Do not commit transcripts. If they were tracked
historically, remove them from the index (`git rm -r --cached sessions/`).
