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
