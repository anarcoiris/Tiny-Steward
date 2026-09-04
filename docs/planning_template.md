# Resumen de Revisión de Hito — Tarea {{task_num}}

- **Sesión ID:** `{{session_id}}`
- **Fecha / Timestamp:** `{{timestamp}}`
- **Agente / Modelo:** `{{agent_name}}` (`{{model_name}}`)
- **Estado de Hito:** `{{status}}` (e.g. COMPLETADO / EN PROGRESO / BLOQUEADO)

---

## 1. Resumen Ejecutivo y Alcance
{{review_text}}

---

## 2. Evidencia Empírica de Validación
> Toda afirmación de progreso debe estar respaldada por una salida observable de herramienta.

- **Comandos / Herramientas ejecutadas:**
  - `{{cmd_or_tool_1}}` → Salida / Exit Code: `{{exit_code_1}}`
  - `{{cmd_or_tool_2}}` → Salida / Exit Code: `{{exit_code_2}}`
- **Artefactos modificados / creados:**
  - [{{file_1}}](file:///{{path_1}})
  - [{{file_2}}](file:///{{path_2}})

---

## 3. Lecciones Aprendidas y Corrección de Errores (si aplica)
- **Fallo / Desviación observada:** {{mistake}}
- **Causa Raíz:** {{root_cause}}
- **Solución Canónica / Fix Permanente:** {{fix_rule}}

---

## 4. Próximos Pasos y Checklist de Tarea
- [ ] {{next_step_1}}
- [ ] {{next_step_2}}
- [ ] {{next_step_3}}

> **Nota de Gobernanza:** Las directivas duraderas del proyecto residen en [`RULES.md`](../RULES.md) y se inyectan en el prompt base. Este documento es un resumen de revisión humana y seguimiento de hitos de sesión.