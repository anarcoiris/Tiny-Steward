# Archivos retirados / absorbidos

Registro de código eliminado o absorbido en el ciclo P5+ (2026-07-16), para que no parezca un borrado accidental.

---

## `core/micro_agent.py` — **eliminado**

| | |
|---|---|
| **Qué era** | Stub Phase-2: clase `MicroAgent` que armaba un system prompt de skill agent y llamaba `atomic_llm.chat()` en un solo turno (sin loop de tools, sin mailbox, sin pane). |
| **Por qué se retiró** | Duplicaba la lógica ya viva en `Runtime._build_delegate_system_prompt` + `_run_delegate_loop` / `_delegate_with_terminal`. Los tests y el path de producción divergían; el stub no usaba tool-calling ni hijos out-of-process. |
| **Dónde vive ahora** | Prompt de especialista: `Runtime._build_delegate_system_prompt(skill)`. Loop de tools en atomic: `Runtime._run_delegate_loop`. Spawn WT/tmux/console: `Runtime._delegate_with_terminal` + `core/delegate_terminal.py`. Entrada child: `steward.py --delegate-mode` → `Runtime.run_delegate_child`. |
| **Tests** | `tests/test_delegate.py` ya no importa `MicroAgent`; cubre `_build_delegate_system_prompt` y `_execute_action(delegate)`. |
| **Recuperar** | `git log -- core/micro_agent.py` / `git show <commit>:core/micro_agent.py` si hace falta el stub histórico. No reintroducir en el import path. |

---

## Cambios relacionados (no son borrados de módulo, pero sí “salidas” del diseño viejo)

| Ítem | Qué pasó |
|------|----------|
| Ejemplos largos en `SYSTEM_PROMPT` (mkdir/read/pwsh/delegate Acme NDA) | Recortados a **un** ejemplo `<tool_call>` (ls). El stub Acme se rechaza en `delegate` (`DELEGATE_EXAMPLE_STUB`). |
| `/set thinking` → `extra_params` plano | Reemplazado por `chat_template_kwargs.enable_thinking` (alias documentado). |
| `_THINK_RE` en display (strip silencioso) | Eliminado; `<think>` / reasoning se muestran (dim en stream). |
| OpenClaw bajo `skills/_meta/{delegation-gate,…}` | **No borrados del disco**; excluidos del index (`OPENCLAW_META_EXCLUDE` en `skill_loader.py`). Quedan `primitives/` y `troubleshooting/`. |

---

## Cómo comprobar que no hay imports huérfanos

```bash
rg "micro_agent|MicroAgent" --glob "*.py"
# esperado: solo comentarios/docs/tests que mencionen el retiro
```
