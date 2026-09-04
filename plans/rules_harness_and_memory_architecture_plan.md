# 🏗️ Plan de Acción e Investigación: Harness, Reglas Tripartitas, Subagentes Atómicos, Topología Multi-GPU y Memoria

> **Nota:** Este documento es el enlace operativo del plan maestro unificado ubicado en [`docs/rules_harness_and_memory_architecture_plan.md`](../docs/rules_harness_and_memory_architecture_plan.md).

Para consultar la especificación completa, los diagnósticos detallados, diagramas de arquitectura, matrices de investigación experimental (R1 a R4) y los planes de acción técnica (A1 a A6), refiérase al documento maestro en `docs/`.

---

## 🎯 Síntesis de los 6 Ejes del Plan Unificado (v2.0.0)

1. **[Eje 1 - P0] Harness de Bootstrapping, Estabilidad LCP y Taxonomía Tripartita:**
   - **Diagnóstico:** Concatenación de L0 a L3 en `core/system_prompt.py`; caídas de LCP a 0% por mutaciones en el prefijo.
   - **Investigación (R1.1, R1.2):** Benchmarking de reuso de KV-Cache en `llama.cpp` y auditoría de límites de caracteres (< 3.500 chars).
   - **Acción (A1.1–A1.3):** Inmutabilidad estricta de Capas L0/L1, refactorización de `RULES.md` (Hard/Soft) y guardrails deterministas en runtime.
   - **Taxonomía:** Reglas Globales (mínimas/invariantes), Reglas Locales (metadatos de control/skills/estados) y Reglas de Sesión (`task.md`).
2. **[Eje 2 - P0] Inmunización contra Sugestión, Complacencia (Sycophancy) y Guardarraíles de Contención:**
   - **Diagnóstico:** Validación acrítica de hipótesis no probadas; anclaje por stubs; fuga de workspace; mutación destructiva de skills y bucles de oscilación en rethink (*thrashing*).
   - **Investigación (R2.1, R2.2):** Test suites adversarias y análisis de atracción por ejemplos.
   - **Acción (A2.1–A2.7):** Precedencia de evidencia empírica (`exit_code == 0`), desanclaje de stubs, **Workspace Sandboxing (G1)**, **Skill Immutability Lock (G2)**, **Circuit-Breaker Anti-Thrashing (G3)** e **Introspección Determinista de APIs ante TypeError/AttributeError (G4)**.
3. **[Eje 3 - P1] Subagentes Atómicos ('Execution Workers' Sin Cuestionar):**
   - **Diagnóstico:** Sobrecarga y toxicidad de contexto heredado en lanes atómicos.
   - **Investigación (R3.1, R3.2):** Eficiencia de token budget (< 24k ctx) vs contexto heredado.
   - **Acción (A3.1–A3.3):** Task Contract Spec, límite estricto de 16k–24k tokens con 1-2 encodings + rethink breve, y retorno estructurado vía `Mailbox`.
4. **[Eje 4 - P1] Topología Multi-GPU (GTX 1080 / 1070) y Backend Gate:**
   - **GPU0 (GTX 1080):** Display principal y GUI protegido; opción de contenedor Docker atómico ultraligero (~32k ctx display-safe).
   - **GPU1 y GPU2 (2x GTX 1070):** Cómputo paralelo local en `llama.cpp` (`orch` y `atomic`).
   - **`backends.gate`:** Arbitraje de slots y prioridades (`interactive` > `dream` > `background`) para una sola terminal interactiva.
5. **[Eje 5 - P0] Jerarquía de Memoria y Protocolo de Promoción:**
   - **Pirámide Ontológica:** `Scratchpad (L5)` < `RAG (L4)` < `lessons.md (L3)` < `task.md (L2)` < `RULES.md (L1)`.
   - **Acción (A5.1–A5.3):** Blindaje de `task.md` y `memory.md` en `RuntimeCompactionMixin`, pipeline sanitizado en `/dream` y auditorías anti *Rule Creep*.
6. **[Eje 6 - P2] Plantilla de Revisión Formal (`docs/planning_template.md`):**
   - Estandarización de revisiones con evidencia observable, causas raíz y checklist trazable.
