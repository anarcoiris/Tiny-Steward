# Resumen de Revisión de Hito — Tarea 9: Diagnóstico Forense del Crash en `/dream` y Auditoría Integral del Código Base

- **Sesión ID / Nombre:** `code-review-mafiabot`
- **Fecha / Timestamp:** `2026-09-04 23:35:00 +02:00`
- **Agente / Modelo:** `Antigravity / Gemini 3.7 Flash (High)`
- **Estado de Hito:** `COMPLETADO (Investigación y Auditoría)`

---

## 1. Resumen Ejecutivo y Diagnóstico Forense del Crash

Al ejecutar el comando de usuario `/dream` en la sesión interactiva `code-review-mafiabot`, el proceso principal `steward.py` colapsó súbitamente con un `httpx.HTTPStatusError: Server error '500 Internal Server Error' for url 'http://127.0.0.1:11800/v1/chat/completions'`.

### 1.1. Cadena de Propagación del Fallo
1. **Invocación:** El usuario ejecuta `/dream` -> `core/runtime.py:run_interactive()` delega en `core/runtime_meta.py:_handle_meta_command()`.
2. **Selección de LLM:** `_handle_dream()` escoge `llm = self.atomic_llm or self.llm`. Dado que `atomic` está presente en `config.yaml`, se utiliza el cliente `atomic`.
3. **Ausencia de Guardias de Excepción:**
   - En `core/runtime_meta.py:_handle_dream()` se llama a `run_dream()` **sin un bloque `try...except`**.
   - En `core/dreaming.py:run_dream()` se llama a `llm.chat(messages, tools=None)` **sin un bloque `try...except`**.
   - En `core/runtime.py:run_interactive()` se llama a `_handle_meta_command()` **sin un bloque `try...except`**.
4. **Fallo en Gateway / Backend:**
   - La petición es enviada a `http://127.0.0.1:11800` (contenedor Docker `docker-ollama-guard` proxy / `python -m guard`).
   - El proxy guard devolvió `500 Internal Server Error` debido al agotamiento del límite de compromiso de memoria virtual (Commit Charge / Pagefile exhaust) en el sistema anfitrión Windows al intentar cargar/procesar el contexto de `qwen3.8-128k`.
5. **Ceguera de Diagnóstico y Ausencia de Fallbacks:**
   - `core/llm.py:_post()` ejecuta `resp.raise_for_status()`, descartando completamente el payload JSON explicativo de error de `resp.text`.
   - `core/llm.py:chat()` solo activa el mecanismo de fallback si `self.fallback_providers` tiene elementos. En `config.yaml`, el bloque `atomic` no tiene configurado ningún fallback (a diferencia de `orchestrator`), por lo que re-lanza el error primario sin alternativa.
   - El traceback no capturado sube hasta el hilo principal de Python, matando el REPL y abortando la sesión interactiva del usuario.
6. **Inconsistencia de Esquema de Trazas:**
   - En `code-review-mafiabot.think.jsonl`, el campo temporal está grabado como `"timestamp": <float>`, mientras que `core/dreaming.py` espera `"ts"`. Esto ocasiona que el filtrado de marcas de agua y la generación de resúmenes queden desfasados o con marcas vacías.

---

## 2. Auditoría Integral del Repositorio desde `core/llm.py`

Partiendo de la capa de inferencia y extendiendo el análisis concéntricamente a todo el sistema:

### 2.1. Capa de Modelos y Clientes LLM (`core/llm.py` y `core/providers/`)
- **Filtrado incompleto de `_build_body`:** Se filtran únicamente claves explícitas (`chat_template_kwargs`, `thinking_budget_tokens`, `cache_prompt`, `id_slot`, `launch`, `fallbacks`). Opciones como `enable_thinking`, `preserve_thinking`, `vision`, `profile`, `expect_total_slots`, etc. quedan en `extra_params` y se inyectan en el JSON de `/v1/chat/completions`. En servidores estrictos (Ollama, vLLM, llama-server nativo), parámetros no estándar provocan errores 400/500.
- **Opacidad de errores HTTP:** `_post()` debe capturar `resp.text` al producirse un fallo HTTP (4xx/5xx) y adjuntarlo a una excepción estructurada (`LLMBackendError`), permitiendo saber con precisión si falló por OOM, falta de VRAM, contexto excedido o parámetros inválidos.
- **Asimetría de Resiliencia entre Lanes:** `orchestrator` posee 3 proveedores fallback (GitHub Models, Groq, OpenRouter), pero `atomic` carece de ellos. Se debe permitir que `atomic` herede fallbacks de `orchestrator` o disponga de su propia cadena fallback.

### 2.2. Capa de Memoria y Consolidación (`core/dreaming.py`, `core/idle_loop.py`)
- **Fragilidad en Hilos de Fondo:** En `core/idle_loop.py:_do_dream_check()`, se invoca `run_dream()` sin aislar errores de red o del LLM. Aunque el bucle maestro tiene un bloque `except`, cualquier fallo no capturado a nivel de función ensucia los estados y puede interrumpir la secuencia de tareas ociosas.
- **Normalización de Trazas `ts` vs `timestamp`:** Es mandatorio unificar el acceso a timestamps: `ts = str(e.get("ts") or e.get("timestamp") or "")`.
- **Límite de Entrada Preservador:** `DREAM_INPUT_CAP` (12.000 caracteres) trunca el texto de forma abrupta si las trazas son extensas, pudiendo cortar fragmentos JSON intermedios.

### 2.3. Capa de Runtime Interactivo (`core/runtime.py`, `core/runtime_meta.py`, `core/runtime_loop.py`)
- **El "Talón de Aquiles" de los Meta-Comandos:** En `runtime.py:run_interactive()`, los comandos que inician con `/` carecen de una red de seguridad global. Un error inesperado en `/dream`, `/stats`, `/mcp` o `/reindex` termina la sesión interactiva completa. Debe envolverse con un bloque defensivo que capture `Exception`, imprima el error con formato amigable y mantenga al usuario en el REPL.
- **Aislamiento de Errores en `_handle_dream`:** Debe envolverse la invocación de `run_dream` en un bloque `try...except`, informando al usuario del problema sin abortar.

### 2.4. Capa de Facade Headless (`core/service_kernel.py`)
- `StewardEngine` proporciona una interfaz headless de alto nivel para CLI, Web API y MCP. No obstante, `StewardEngine.dream()` asume que `run_dream()` no levantará excepciones. Si se integra en servicios desatendidos (FastAPI / WebSockets), un fallo del LLM causará un error 500 no controlado en la API web.

### 2.5. Capa de Primitivas y Sistema de Archivos (`core/primitives.py`, `core/shell_guard.py`)
- La normalización de saltos de línea CRLF implementada en la Tarea 8 ha demostrado total estabilidad (238 tests pasando exitosamente).
- `core/runtime_execution.py` desvía salidas mayores a 50 líneas hacia `.temp/`, protegiendo la ventana de contexto de forma ejemplar.

### 2.6. Gobernanza de Sesiones y Estructura en Disco
- Se detectan ficheros de sesiones legacy en la raíz de `sessions/` que no respetan la estructura de carpetas homónimas exigida por las reglas de gobernanza. Las nuevas sesiones (`sessions/code-review-mafiabot`) sí se adhieren al estándar conteniendo sus archivos de interacción, trazas, `task.md` y `plan.md`.

---

## 3. Próximos Pasos y Plan de Acción Técnico
- [ ] **Paso 1:** Implementar captura y extracción de detalles de error (`resp.text`) en `core/llm.py:_post()`.
- [ ] **Paso 2:** Sanitizar los parámetros enviados a `/v1/chat/completions` en `core/llm.py:_build_body()` para depurar claves internas.
- [ ] **Paso 3:** Blindar con `try...except` las invocaciones de `run_dream()` en `core/dreaming.py`, `core/runtime_meta.py`, `core/idle_loop.py` y `core/service_kernel.py`.
- [ ] **Paso 4:** Proteger `run_interactive()` en `core/runtime.py` con un guardia global ante excepciones en meta-comandos.
- [ ] **Paso 5:** Normalizar el soporte dual para `ts` y `timestamp` en `core/dreaming.py`.
- [ ] **Paso 6:** Configurar fallbacks para el carril `atomic` en `config.yaml` o permitir fallback al modelo orchestrator.
- [ ] **Paso 7:** Validar con la suite de pruebas unitarias (`pytest`).
