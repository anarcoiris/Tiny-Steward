# 🛰️ Extrapolación Arquitectónica y Aprendizajes de PulseLab Forge para Tiny-Steward

**Documento:** `docs/ideas/PULSE_TO_TINY_STEWARD_LEARNINGS.md`  
**Fecha:** 2026-08-30  
**Autor:** Antigravity Pairing System (Wingman Agent)  
**Objetivo:** Análisis comparativo exhaustivo del repositorio principal de Pulse (`main` branch) y de su evolución de calibración (`dev-backup`) para extraer lecciones clave, patrones arquitectónicos y mejoras de alto impacto para Tiny Steward.

---

## 1. 🔍 Resumen Ejecutivo

Tanto **PulseLab Forge** como **Tiny Steward** comparten un ADN común dentro del ecosistema de agentes:
- Operan sobre modelos locales y soberanos (**Qwythos 9B**, **Qwen 3 4B Atomic**, **llama.cpp / Ollama**).
- Minimizan el despilfarro de contexto mediante políticas estrictas de KV cache (`cache_prompt`, prompt prefix preservation).
- Implementan arquitecturas de doble carril (**Orchestrator** para razonamiento profundo + **Atomic** para operaciones rápidas/deterministas).

Sin embargo, **Pulse** ha atravesado una fase intensiva de consolidación arquitectónica, auditoría de degradación, pruebas de regresión con fixtures (198 tests), inmunización de bases de datos vectoriales y exposición mediante **FastMCP (36 herramientas)**. 

Tiny Steward puede acelerar exponencialmente su madurez adoptando estos patrones probados sin tener que tropezar con los mismos escollos.

---

## 2. 🏛️ Aprendizajes Clave de la Rama `main` de Pulse

### 2.1. Kernel de Servicio Unificado (`PulseLabEngine`)
* **Qué hace Pulse:** En `core/service_kernel.py`, todo el ciclo de vida del diseño (síntesis $\to$ simulación $\to$ colocación $\to$ ruteo $\to$ vertidos $\to$ auditoría DRC $\to$ exportación) está encapsulado en una única clase maestra `PulseLabEngine`. Esta clase es consumida indistintamente por FastAPI (`app/main.py`), FastMCP (`mcp_server/server.py`), la terminal interactiva (`studio/`) y scripts SDK.
* **Lección para Tiny Steward:** Actualmente, `tiny_steward` tiene lógica de ejecución distribuida entre `steward.py`, `core/runtime_loop.py`, `core/runtime_execution.py` y `serve.py`. Extraer un **`StewardEngine`** desacoplado permitirá que Tiny Steward sea ejecutado como librería Python, servidor FastMCP, backend Web o CLI sin duplicación de lógica.

### 2.2. Sistema de Reglas Determinista por Fases y Contrato Estructurado (`finding.schema.json`)
* **Qué hace Pulse:**
  1. `core/RULES.md` define fases ordenadas estrictamente por **dependencia** (Fase 0: Sintaxis $\to$ Fase 1: Footprints $\to$ Fase 2: Nets $\to$ Fase 3: Topología $\to$ Fase 4: DRC $\to$ Fase 5: Paridad SCH $\leftrightarrow$ PCB). No se evalúan fases avanzadas si la base está rota.
  2. `skills/finding.schema.json` formaliza un contrato estricto de hallazgos (`rule_id`, `domain`, `severity`, `refs`, `message`, `suggested_fix: {action, details}`, `confidence`). El LLM no recibe prosa vaga para corregir errores, sino órdenes de acción estructuradas.
* **Lección para Tiny Steward:** Tiny Steward puede incorporar un validador de fases y un esquema de hallazgos estructurados para sus revisiones de código, creación de `skills` y validación de planes. Cuando un subagente falla, en lugar de pasarle un volcado de error sin procesar, se le entrega un `Finding` estructurado que puede solucionar de forma determinista.

### 2.3. Exposición Completa vía FastMCP (Model Context Protocol)
* **Qué hace Pulse:** `mcp_server/server.py` implementa 36 herramientas FastMCP con imports perezosos (`lazy loading`) y esquemas tipados. Esto permite que agentes de alto nivel (Claude Desktop, Antigravity IDE) consuman Pulse como si fuera una API nativa.
* **Lección para Tiny Steward:** Tiny Steward puede exponer su propio servidor FastMCP (`mcp_server/`) con herramientas como `steward_execute_turn`, `steward_dream`, `steward_lookup_skill`, `steward_delegate_task`, permitiendo que el Wingman Agent y otros entornos deleguen tareas complejas directamente a Tiny Steward como herramienta MCP.

### 2.4. Resiliencia de Proveedores y Caché Local en Disco
* **Qué hace Pulse:** `core/provider_fetcher.py` consulta catálogos (JLCPCB, PCBWay) y almacena respuestas en `knowledge/cache/provider_components_cache.json` con TTL de 24h, fallbacks sin conexión y normalización de esquemas.
* **Lección para Tiny Steward:** Aplicar este patrón de caché local persistente con huella SHA-256 para consultas de extensiones, grafos de skills ensamblados y peticiones a backends remotos/locales.

---

## 3. 🛡️ Aprendizajes de la Rama de Desarrollo (`dev-backup`) y Calibración

### 3.1. Inmunización de RAG y Memoria (`RAG_HYGIENE_AND_IMMUNIZATION_BLUEPRINT.md`)
* **El Peligro Descubierto en Pulse:** Durante los ciclos de síntesis fallidos, el sistema guardaba trazas de error (`passed=false`) en `knowledge/experiences/`. El motor RAG las indexaba ciegamente, provocando que el LLM recuperara "redes flotantes" o mensajes de depuración como si fueran guías autorizadas de diseño (**bucle de envenenamiento de memoria**).
* **Solución de Pulse (Los 5 Pilares de Inmunización):**
  1. *Gatekeeper Hardened:* `passed == True AND drc_violations == 0` obligatorio antes de persistir en memoria de largo plazo.
  2. *Filtro Semántico Heurístico:* Rechazo de cadenas como `"Remediated issue:"`, volcados de consola y logs de debug.
  3. *Cuarentena Aislada:* Archivos fallidos se mueven a `quarantine/`.
  4. *Huella SHA-256 en Manifest:* Detección inmediata de desincronización entre chunks en memoria y vectores en disco.
* **Lección Vital para Tiny Steward (`/dream` y `core/dreaming.py`):**
  Tiny Steward utiliza `/dream` para consolidar razonamiento (`<think>`) en `sessions/<name>.memory.jsonl` y `.memory.md`. Si una sesión falló o tuvo alucinaciones de razonamiento, **soñar sobre ella envenena la memoria a largo plazo**. Tiny Steward debe implementar el mismo *Gatekeeper* en `dreaming.py`: solo consolidar sesiones exitosas o etiquetar explícitamente los anti-patrones en un directorio de cuarentena.

### 3.2. Guardarraíles de Truncación y Agotamiento de Razonamiento (`Session 4c`)
* **Problemas Documentados en Pruebas Reales:**
  1. *Semantic Stub:* El modelo devuelve un JSON válido pero vacío o con cobertura <90%.
  2. *Hard Truncation:* `done_reason == "length"` con contenido cortado.
  3. *Reviewer Truncado:* Todo el presupuesto de tokens (`num_predict` / `max_tokens`) es consumido por las etiquetas `<think>`, dejando `content` vacío.
  4. *Runaway Enumeration:* El modelo alucina cientos de elementos inexistentes.
* **Soluciones Implementadas en Pulse:**
  - `llm_json.parse_llm_result(content, thinking)`: Si el contenido viene vacío porque el modelo agotó sus tokens en `<think>`, extrae el payload estructurado directamente desde el bloque de pensamiento.
  - Normalización de `done_reason` en todas las capas (tanto API nativa de Ollama como OpenAI compatible).
  - Turno de continuación automático: Si el JSON se corta limpiamente por límite de contexto, envía automáticamente `"Continue the JSON from exactly where you stopped. No prose."` y concatena las partes.
* **Lección para Tiny Steward (`core/llm.py` y `core/action_parse.py`):**
  Implementar estas 4 guardas de truncación garantizará que los micro-agentes y el orquestador nunca fallen silenciosamente ante salidas cortadas o saturadas por CoT.

### 3.3. Orquestación Dual-Backend y Control de Contención GPU (`Session 4d`)
* **Descubrimiento en Pulse:** Cuando el proceso principal de síntesis corría en paralelo con la reindexación de embeddings o revisiones atómicas, la GPU GTX 1080 (8GB) experimentaba contención severa (tiempos de inferencia pasaban de 400s a 880s).
* **Solución:**
  - Semáforos explícitos y asignación de roles fijos (`review` y `json_patch` en carril atómico :11439 sin thinking; `synthesis` en orquestador :11440 con thinking).
  - Fallback automático silencioso si el carril atómico se cae.
* **Lección para Tiny Steward:** `backend_gate.py` ya tiene semáforos, pero puede adoptar el enrutamiento por tipo de tarea (ej. enviar `/dream`, validación de argumentos de herramientas y parsing de skills al carril `atomic`, reservando el `orchestrator` para el diálogo interactivo).

### 3.4. Balance Prompt Fijo vs. RAG Dinámico (`prompt_vs_rag_balance.md`)
* **Descubrimiento:** Tener decenas de reglas estáticas en el prompt del sistema crea un sesgo rígido que devora el presupuesto de tokens (KV cache) y bloquea la adaptabilidad.
* **Solución:** Mantener un system prompt esquelético y ultra-conciso, inyectando dinámicamente solo las reglas y experiencias relevantes al contexto específico mediante embeddings de alta fidelidad.
* **Lección para Tiny Steward:** Proteger `RULES.md` para que permanezca compacto (menos de 60 líneas) y mover reglas operativas detalladas a skills indexadas bajo demanda.

---

## 4. 📋 Plan de Acción Recomendado para Tiny Steward

| Prioridad | Módulo / Área | Mejora Propuesta | Origen del Patrón |
|---|---|---|---|
| **P0** | `core/dreaming.py` | **Inmunización de Memoria:** Añadir filtro gatekeeper para evitar consolidar sesiones fallidas o logs de depuración corruptos. | `RAG_HYGIENE_AND_IMMUNIZATION_BLUEPRINT.md` |
| **P0** | `core/llm.py` & `action_parse.py` | **Guardas de Truncación y Rescate de Think:** Función `parse_llm_result` para recuperar tool calls cuando el thinking satura la respuesta, y soporte de turno de continuación. | `test_llm_truncation_guards.py` |
| **P1** | `core/service_kernel.py` | **`StewardEngine` Unificado:** Consolidar el ciclo de vida del agente desacoplándolo de la interfaz de consola REPL. | `core/service_kernel.py` (`PulseLabEngine`) |
| **P1** | `mcp_server/` | **Servidor FastMCP de Tiny Steward:** Exponer primitivas, skills y delegación de tareas como herramientas MCP nativas. | `Pulse-main/mcp_server/server.py` |
| **P2** | `DomainSpec/` & `skills/` | **Contrato `finding.schema.json`:** Esquema estructurado de hallazgos y correcciones para subagentes y revisiones de código. | `skills/finding.schema.json` |
| **P2** | `docs/status/` | **Dashboard de Estado y Roadmap Activo:** `STEWARD_STATUS.md` y `CURRENT_SPRINT.md` para visibilidad continua de hitos. | `docs/status/FORGE_STATUS.md` |

---

## 5. 🎯 Conclusión

PulseLab Forge ha desarrollado un ecosistema industrial de validación, resiliencia y gobernanza de agentes de IA locales que resuelve exactamente los desafíos de fiabilidad que afronta Tiny Steward. La implementación progresiva de estas mejoras dotará a Tiny Steward de una robustez superior frente a truncaciones, una memoria a largo plazo inmunizada contra alucinaciones y una interfaz FastMCP estandarizada para cooperar fluidamente con su Wingman Agent.
