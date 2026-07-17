# Fuera de alcance → siguiente ciclo (F1+)

**Origen:** diferidos del plan multiphase + post P0–P8.  
**Archivo histórico:** [`archive/`](archive/)  
**Operador:** [`docs/operator.md`](../docs/operator.md)  
**Retiros:** [`archivos-retirados.md`](archivos-retirados.md)

P0–P8 y F1–F2 **hechos**. También (2026-07-16 noche):

- Parser tolera `<path>` / hybrid `</parameter>`; ejemplo `write` en SYSTEM_PROMPT
- `/attach` + `@path` para transcripts largos (sin pegar)
- Nudge si solo hay think sin tool_call
- Skills `_meta/primitives` en formato `<tool_call>`
- `sessions/` untracked; playbook de operador

**F7 (2026-07-17) hecho:**

- Prompt hygiene: refuse pasted REPL chrome; scrub outbound; empty think-only placeholder
- Client `backends.gate` for orch/atomic/embed (interactive > dream)
- `/dream` + `/memory` → `*.memory.jsonl` / `*.memory.md`; compact prefers memories

```mermaid
flowchart TD
  f3[F3_parallel_slots]
  f4[F4_slot_save_restore]
  f5[F5_vision_mmproj]
  f6[F6_ui_zoom]
  f3 --> f4
  f5
  f6
```

---

## Orden restante

1. **F3** — `--parallel N` + `id_slot` por child (ops host + cliente)  
2. **F4** — Slot save/restore unificado con árbol de sesiones  
3. **F5** — Vision / mmproj (camino mínimo)  
4. **F6** — Zoom de fuente por emulador (bajo ROI)

---

## Checklist

- [x] f1-abort-lcp  
- [x] f2-rules-md  
- [x] tool-call-write-hardening + attach-by-path + think-nudge + operator docs  
- [x] f7-prompt-hygiene-gate-dreaming  
- [ ] f3-parallel-id-slot  
- [ ] f4-slot-save-restore  
- [ ] f5-vision-mmproj  
- [ ] f6-font-zoom  
