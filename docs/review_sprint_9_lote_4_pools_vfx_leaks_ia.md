# Resumen de Revisión de Hito — Sprint 9: Lote 4 (Pools, VFX, Leaks e IA Bio-Neuromórfica)

- **Sesión ID:** `revision_roadmap_global_y_sincronizacion_md`
- **Fecha / Timestamp:** `2026-09-26 00:44:00 +02:00`
- **Agente / Modelo:** `Antigravity` (`Gemini 3.7 Flash High`)
- **Estado de Hito:** `COMPLETADO (18/18 Suites Headless PASS)`

---

## 1. Resumen Ejecutivo y Alcance
Se completó con éxito el **Lote 4 de Sprint 9**, enfocado en la estabilidad del motor, object pooling de VFX, prevención de fugas de memoria (ObjectDB leaks) y robustecimiento de la capa de reflejos bio-neuromórficos de la IA en colaboración con el Wingman Tiny-Steward.

### 1.1. Bugs Resueltos y Soluciones Aplicadas:
1. **BUG-25 (Re-Entrancia y Duplicación en ParticlePool):**
   - En `ParticlePool.gd`, se añadió una comprobación estricta de pertenencia previa (`if _available_explosions.has(exp_node): return`) en `return_explosion()` y `reset_all()`.
   - Se implementó `cleanup_immediate()` en `CyberExplosion.gd` y `EpicExplosion.gd` para matar tweens activos antes del retorno al pool.
2. **BUG-26 (Apagado de Humo GPU en CyberExplosion):**
   - En `_on_cleanup()` y `cleanup_immediate()`, se forzó `smoke_particles.emitting = false` al reciclar explosiones pooled, eliminando el consumo invisible de GPU fuera de pantalla.
3. **BUG-27 (Desconexión de Señales en `_exit_tree()`):**
   - Implementado `_exit_tree()` desconectando `GameSettings.settings_changed` y señales globales en `LightCycle.gd`, `LightWallManager.gd`, `UltraCycleLights.gd`, `CockpitInterior.gd`, `CockpitHUD.gd`, `UltraCityBuilder.gd`, `UltraEnvironmentManager.gd` y `VirtualTouchControls.gd`.
   - Reducción drástica de fugas de `ObjectDB instances leaked at exit`.
4. **BUG-28 (Deduplicación de Eventos en InputManager):**
   - En `_register_key_and_joy()` y `_register_joy_action()`, se agregó `InputMap.action_erase_events(action)` si la acción ya existía, erradicando la acumulación multiplicativa de eventos en el InputMap.
5. **BUG-30 (Filtro de Velocidad de Aproximación en IA Neuromórfica):**
   - En `NeuromorphicReflexController.gd`, se añadió `prev_heading`. Al cambiar de rumbo o al spawnear, se resetea la distancia previa para no comparar ejes ortogonales.
   - Se acotó la derivada temporal de aproximación a `current_speed * 2.5`, erradicando spikes espurios de Looming que provocaban giros de pánico sin obstáculos.

---

## 2. Evidencia Empírica de Validación
- **Suite Específica:** Creada `scenes/tests/TestBatch4PoolsAndVfxScene.tscn` / `scripts/tests/test_batch4_pools_and_vfx.gd` -> **5/5 PASS (Exit Code: 0)**.
- **Batería Maestra:** Integrada en `run_all_tests.ps1`:
  - **Resultado:** **18/18 SUITES PASARON AL 100% (Exit Code: 0)**.
- **Artefactos Modificados:**
  - [`scripts/arena/ParticlePool.gd`](file:///c:/Users/soyko/Documents/TacticalAssassin/Lightbikes/scripts/arena/ParticlePool.gd)
  - [`scripts/CyberExplosion.gd`](file:///c:/Users/soyko/Documents/TacticalAssassin/Lightbikes/scripts/CyberExplosion.gd)
  - [`scripts/vfx/EpicExplosion.gd`](file:///c:/Users/soyko/Documents/TacticalAssassin/Lightbikes/scripts/vfx/EpicExplosion.gd)
  - [`scripts/LightCycle.gd`](file:///c:/Users/soyko/Documents/TacticalAssassin/Lightbikes/scripts/LightCycle.gd)
  - [`scripts/LightWallManager.gd`](file:///c:/Users/soyko/Documents/TacticalAssassin/Lightbikes/scripts/LightWallManager.gd)
  - [`scripts/cycle/UltraCycleLights.gd`](file:///c:/Users/soyko/Documents/TacticalAssassin/Lightbikes/scripts/cycle/UltraCycleLights.gd)
  - [`scripts/cycle/CockpitInterior.gd`](file:///c:/Users/soyko/Documents/TacticalAssassin/Lightbikes/scripts/cycle/CockpitInterior.gd)
  - [`scripts/CockpitHUD.gd`](file:///c:/Users/soyko/Documents/TacticalAssassin/Lightbikes/scripts/CockpitHUD.gd)
  - [`scripts/arena/UltraCityBuilder.gd`](file:///c:/Users/soyko/Documents/TacticalAssassin/Lightbikes/scripts/arena/UltraCityBuilder.gd)
  - [`scripts/arena/UltraEnvironmentManager.gd`](file:///c:/Users/soyko/Documents/TacticalAssassin/Lightbikes/scripts/arena/UltraEnvironmentManager.gd)
  - [`scripts/ui/VirtualTouchControls.gd`](file:///c:/Users/soyko/Documents/TacticalAssassin/Lightbikes/scripts/ui/VirtualTouchControls.gd)
  - [`scripts/core/InputManager.gd`](file:///c:/Users/soyko/Documents/TacticalAssassin/Lightbikes/scripts/core/InputManager.gd)
  - [`scripts/ai/NeuromorphicReflexController.gd`](file:///c:/Users/soyko/Documents/TacticalAssassin/Lightbikes/scripts/ai/NeuromorphicReflexController.gd)
  - [`run_all_tests.ps1`](file:///c:/Users/soyko/Documents/TacticalAssassin/Lightbikes/run_all_tests.ps1)
  - [`task.md`](file:///c:/Users/soyko/Documents/TacticalAssassin/Lightbikes/task.md)
  - [`plan.md`](file:///c:/Users/soyko/Documents/TacticalAssassin/Lightbikes/plan.md)
  - [`docs/master_plan_work_roadmap.md`](file:///c:/Users/soyko/Documents/TacticalAssassin/Lightbikes/docs/master_plan_work_roadmap.md)

---

## 3. Lecciones Aprendidas y Directrices de Robustez
- **Fallo observado:** Conexiones directas a señales de singletons (`GameSettings.settings_changed`) sin desconexión en `_exit_tree()` mantienen vivos objetos referenciados por el runtime de Godot, acumulando advertencias de fugas.
- **Solución Canónica:** Cualquier nodo que se conecte a un Autoload singleton DEBE implementar `_exit_tree()` con desconexión explícita `if Singleton.signal.is_connected(handler): Singleton.signal.disconnect(handler)`.
- **Object Pooling:** Todo nodo devuelto a un pool debe tener un método idempotente `cleanup_immediate()` que aniquile tweens y apague emisores GPU antes de reingresar a la lista de disponibles.

---

## 4. Próximos Pasos (Secuencia Inmediata de Roadmap)
- [ ] Ejecutar **Lote 2**: Cámaras Cinematográficas y Estabilidad Visual (BUG-21, BUG-22, BUG-29, BUG-34).
- [ ] Ejecutar **Lote 3**: Red y Simulación Autoritativa (BUG-06, BUG-17, BUG-31, BUG-32).
- [ ] Ejecutar **Lote 5**: Polish y Validación Headless Final (BUG-11, BUG-12, BUG-15).
