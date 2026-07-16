# Archivos retirados / absorbidos

Registro de código eliminado o absorbido (2026-07-16), para que no parezca un borrado accidental.

---

## `core/micro_agent.py` — **eliminado**

| | |
|---|---|
| **Qué era** | Stub Phase-2: clase `MicroAgent` que armaba un system prompt de skill agent y llamaba `atomic_llm.chat()` en un solo turno (sin loop de tools, sin mailbox, sin pane). |
| **Por qué se retiró** | Duplicaba la lógica ya viva en `Runtime._build_delegate_system_prompt` + `_run_delegate_loop` / `_delegate_with_terminal`. |
| **Dónde vive ahora** | `Runtime` delegate paths + `core/delegate_terminal.py` + `steward.py --delegate-mode`. |
| **Recuperar** | `git show <commit>:core/micro_agent.py` — no reintroducir en el import path. |

---

## Skills `_meta/primitives/*.md` — **reescritas**

De `<action name="…">` legacy → `<tool_call>/<parameter=…>` nativo (evita que `help()` enseñe un dialecto que el modelo mezclaba con `<path>` bare).

---

## Sesiones en git — **untracked**

`sessions/*.json` y `*.interactions.jsonl` salieron del índice (`git rm --cached`). Quedan en disco. Ver `docs/operator.md`.

---

## Otros

| Ítem | Qué pasó |
|------|----------|
| SYSTEM_PROMPT ejemplos largos / Acme NDA | Recortados; ejemplos `ls` + `write` con `<parameter=…>` |
| `/set thinking` → extra_params | → `chat_template_kwargs`; `medium` se rechaza |
| Pegar transcripts | → `/attach` y `@path` |
| OpenClaw `_meta/{delegation-gate,…}` | Excluidos del index; archivos en disco |
