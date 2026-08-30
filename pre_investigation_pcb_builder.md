# Refactor Steward.py & Web Agent for Async Orchestration and Hierarchical Planning

Este documento detalla el plan para implementar la arquitectura de **subagente atómico asíncrono** y el manejo de **planes jerárquicos**, permitiendo al Orquestador coordinar múltiples sub-agentes sin bloqueo, y a la UI mostrar su estado en tiempo real.

## User Review Required

> [!WARNING]
> **Nuevas Primitivas de LLM**
> Se introducirán nuevas primitivas en `system_prompt.py` para el Orquestador:
> - `delegate_async(agent, task)`: Lanza un subagente y retorna un `session_id` inmediatamente, sin bloquear.
> - `check_delegate(session_id)`: Consulta el estado de un subagente asíncrono.
> - `wait_delegate(session_id)`: Bloquea hasta que un subagente asíncrono termine.
> ¿Estás de acuerdo con añadir estas nuevas herramientas, o prefieres modificar la primitiva `delegate` existente para que acepte un argumento opcional como `async=true`?

> [!IMPORTANT]
> **Formato de Planes Jerárquicos (`task.md`)**
> Propongo utilizar la indentación estándar de Markdown para representar tareas y micro-tareas (sub-tasks).
> Ejemplo:
> ```markdown
> - [ ] Tarea Principal 1
>   - [ ] Micro-tarea 1.1 (asignable a subagente)
>   - [ ] Micro-tarea 1.2
> ```
> El backend parseará esto y el Kanban de la web UI lo mostrará como tarjetas con "sub-tareas" anidadas. ¿Es este formato suficiente para tus necesidades de desglose?

## Proposed Changes

---

### Core Runtime & Orchestrator Awareness

Implementar la ejecución asíncrona de delegados y proporcionar herramientas al Orquestador para gestionarlos.

#### [MODIFY] [core/runtime_delegate.py](file:///c:/Users/soyko/Documents/tiny_steward/core/runtime_delegate.py)
- Añadir el método `_delegate_async_with_terminal(self, skill, problem, context_text)` que realiza el mismo proceso de `spawn_child` pero retorna inmediatamente el `child_name` sin llamar a `_wait_for_delegate_result`.
- Implementar `check_delegate(child_name)` para leer la metadata de la sesión (`status`, `result`) y el buzón (mailbox) para ver si ha terminado.

#### [MODIFY] [core/runtime_execution.py](file:///c:/Users/soyko/Documents/tiny_steward/core/runtime_execution.py)
- Añadir acciones `delegate_async`, `check_delegate` y `wait_delegate` al despachador principal de acciones del Orquestador.

#### [MODIFY] [core/system_prompt.py](file:///c:/Users/soyko/Documents/tiny_steward/core/system_prompt.py)
- Actualizar `SYSTEM_PROMPT` para documentar estas 3 nuevas herramientas y enseñar al Orquestador a dividir problemas en sub-tareas y lanzarlas en paralelo con `delegate_async`.

#### [MODIFY] [core/runtime_meta.py](file:///c:/Users/soyko/Documents/tiny_steward/core/runtime_meta.py) (o similar, en el context injector)
- Inyectar periódicamente (ej. en el prompt del idle loop o en cada turno) una nota indicando: *"You have N background tasks running: child_1, child_2"*, para que el Orquestador sea "consciente" ad-libitum de los procesos activos sin tener que hacer polling manual constante.

---

### Web IDE & Observability

Mostrar las sesiones atómicas en la interfaz y el estado de ejecución.

#### [MODIFY] [core/web_server.py](file:///c:/Users/soyko/Documents/tiny_steward/core/web_server.py)
- Modificar el endpoint `/api/tasks` para parsear listas anidadas de markdown y devolver una estructura jerárquica de tareas y micro-tareas.
- Añadir un nuevo endpoint `/api/delegates/active` que consulte `session_manager.list_sessions()` y devuelva solo las sesiones hijas (`parent == current_session`) que tengan `status == "running"`.

#### [MODIFY] [dashboard.html](file:///c:/Users/soyko/Documents/tiny_steward/dashboard.html)
- Añadir un contador/badge global en la cabecera (junto al Session Select) que muestre el "número de procesos en background siendo ejecutados" (ej. ⚡ 3 Active).
- Añadir una nueva vista rápida en el sidebar o en el menú que liste los procesos atómicos lanzados y su estado (Running, Done, Error).

#### [MODIFY] [web/js/app.js](file:///c:/Users/soyko/Documents/tiny_steward/web/js/app.js) (Asumido)
- Implementar polling al endpoint `/api/delegates/active` para actualizar la UI en tiempo real de los subagentes ejecutándose.
- Adaptar el renderizado del Kanban para soportar/mostrar las micro-tareas anidadas que provienen de `/api/tasks`.

## Verification Plan

### Manual Verification
1. Abrir REPL de `steward.py`.
2. Pedir al agente Orquestador: "Desglosa este problema en 2 tareas y ejecútalas asíncronamente".
3. Verificar en la web UI que el contador de procesos en background sube a 2.
4. Verificar en el Kanban que `task.md` refleja la estructura jerárquica.
5. El Orquestador usará `check_delegate` o `wait_delegate` y procederá cuando terminen, unificando el resultado.
