# Resumen de Revisión de Hito — Tarea 9: Diagnóstico Forense del Crash en `/dream` y Auditoría Integral del Código Base

- **Sesión ID / Nombre:** `code-review-mafiabot`
- **Fecha / Timestamp:** `2026-09-04 23:35:00 +02:00`
- **Agente / Modelo:** `Antigravity / Gemini 3.7 Flash (High)`
- **Estado de Hito:** `COMPLETADO (Investigación y Auditoría)`

---

## 1. Resumen Ejecutivo y Diagnóstico Forense del Crash

Al ejecutar el comando de usuario `/dream` en la sesión interactiva `code-review-mafiabot`, el proceso principal `steward.py` colapsó con `httpx.HTTPStatusError: Server error '500 Internal Server Error' for url 'http://127.0.0.1:11800/v1/chat/completions'`.

### 1.1. Cadena de Propagación del Fallo
1. **Invocación:** El usuario ejecuta `/dream` -> `core/runtime.py:run_interactive()` delega en `core/runtime_meta.py:_handle_meta_command()`.
2. **Selección de LLM:** `_handle_dream()` escoge `llm = self.atomic_llm or self.llm`. Dado que `atomic` está presente en `config.yaml`, se utiliza el cliente `atomic`.
3. **Ausencia de Guardias de Excepción:**
   - En `core/runtime_meta.py:_handle_dream()` se llama a `run_dream()` sin un bloque `try...except`.
   - En `core/dreaming.py:run_dream()` se llama a `llm.chat(messages, tools=None)` sin un bloque `try...except`.
   - En `core/runtime.py:run_interactive()` se llama a `_handle_meta_command()` sin un bloque `try...except`.
4. **Fallo en Gateway / Backend:**
   - La petición es enviada a `http://127.0.0.1:11800` (contenedor Docker `docker-ollama-guard` proxy / `python -m guard`).
   - El proxy guard devolvió `500 Internal Server Error` debido al agotamiento del límite de compromiso de memoria virtual (Commit Charge / Pagefile exhaust) en el sistema anfitrión Windows al intentar cargar/procesar el contexto de `qwen3.8-128k`.
5. **Ceguera de Diagnóstico y Ausencia de Fallbacks:**
   - `core/llm.py:_post()` ejecuta `resp.raise_for_status()`, descartando completamente el payload JSON explicativo de error de `resp.text`.
   - `core/llm.py:chat()` solo activa el mecanismo de fallback si `self.fallback_providers` tiene elementos. En `config.yaml`, el bloque `atomic` no tiene configurado ningún fallback (a diferencia de `orchestrator`), por lo que re-lanza el error primario sin alternativa.
   - El traceback no capturado sube hasta el hilo principal de Python, matando el REPL y abortando la sesión interactiva del usuario.
6. **Inconsistencia de Esquema de Trazas:**
   - En `code-review-mafiabot.think.jsonl`, el campo temporal está grabado como `"timestamp": <float>`, mientras que `core/dreaming.py` espera `"ts"`. Esto ocasiona que el filtrado de marcas de agua y la generación de resúmenes queden desfasados.

---

## 2. Evidencia Empírica y Auditoría del Sistema
- **Pruebas de Conectividad y Health:**
  - `http://127.0.0.1:11800/health` respondió `200 {"status":"ok"}`.
  - `http://127.0.0.1:11800/v1/models` respondió con el catálogo activo (`qwen3.8-128k:latest`, etc.).
  - Docker logs de `ollama-guard` confirmaron la emisión de `500 Internal Server Error` ante la llamada a `/v1/chat/completions`.
  - Agotamiento de commit limit observado en tiempo de ejecución: `ResourceUnavailable: El archivo de paginación es demasiado pequeño para completar la operación` / `GC heap initialization failed with error 0x8007000E`.
- **Suite de Pruebas Automatizadas:**
  - `python -m pytest`: **238 passed** en 27.14s (estabilidad completa de los tests existentes).

---

## 3. Matriz de Auditoría por Componentes (Expansión desde `core/llm.py`)

| Componente | Hallazgo Crítico / Riesgo | Solución Propuesta |
| :--- | :--- | :--- |
| **`core/llm.py`** | Opacidad en `_post`: `resp.raise_for_status()` oculta el mensaje de error del backend. | Extraer `resp.text` en caso de error HTTP e incluirlo en la excepción. |
| **`core/llm.py`** | Fuga de claves internas en `_build_body` hacia el payload JSON de OpenAI. | Sanitizar exhaustivamente `extra_params` antes de enviar el body. |
| **`config.yaml` / Providers** | El lane `atomic` no tiene fallbacks definidos (a diferencia de `orchestrator`). | Permitir que `atomic` herede fallbacks o añadir providers para atomic. |
| **`core/dreaming.py`** | `run_dream()` no captura excepciones del LLM; discrepancia de timestamps (`ts` vs `timestamp`). | Aislar `llm.chat()` con `try...except` y normalizar timestamps. |
| **`core/runtime_meta.py`** | `_handle_dream()` no maneja fallos de `run_dream()`, propagando el crash al REPL. | Envolver la llamada en `try...except` e imprimir mensaje de error limpio. |
| **`core/runtime.py`** | `run_interactive()` ejecuta meta-comandos sin guardia de excepción global. | Proteger el bloque de meta-comandos para evitar abortar el REPL interactivo. |
| **`core/service_kernel.py`** | `StewardEngine.dream()` asume ausencia de excepciones en `run_dream()`. | Añadir manejo de excepciones devolviendo `DreamResult(ok=False, reason=...)`. |
| **`core/idle_loop.py`** | `_do_dream_check()` invoca `run_dream()` en hilo daemon sin aislamiento de red. | Atrapar excepciones específicas y registrar estado en `IdleState`. |

---

## 4. Próximos Pasos y Checklist de Tarea
- [ ] Aplicar la resiliencia en `core/llm.py` (inspección de `resp.text` y sanitización de body).
- [ ] Aplicar los guardias de excepción en `core/runtime_meta.py`, `core/dreaming.py` y `core/runtime.py`.
- [ ] Normalizar el manejo dual de timestamps `ts` / `timestamp` en `core/dreaming.py`.
- [ ] Ejecutar la suite de tests unitarios y añadir pruebas específicas para estas salvaguardas.
- [ ] Acompañar a Tiny-Steward asegurando que aprenda de este incidente y mantenga su estado ordenado.
