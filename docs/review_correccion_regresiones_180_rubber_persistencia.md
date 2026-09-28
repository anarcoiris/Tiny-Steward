# Resumen de Revisión de Hito — Corrección de Regresiones: Físicas de 180°, Rubber Dinámico y Persistencia de Ajustes

- **Sesión ID / Nombre:** `correccion_regresiones_180_rubber_persistencia`
- **Fecha / Timestamp:** `2026-09-23 19:40:00 +02:00`
- **Agente / Modelo:** `Antigravity / Gemini 3.7 Flash (High)`
- **Estado de Hito:** `COMPLETADO (100% PASS - 15 Suites / 67 Tests)`
- **Progreso Global del Proyecto:** `92% Completado`

---

## 1. Resumen Ejecutivo y Objetivos Conquistados

Se ha completado con éxito la corrección y blindaje exhaustivo de las 4 regresiones críticas detectadas en el comportamiento nuclear del juego:

1. **Auto-bloqueos en Esquinas y Colisión con Estela Propia**:
   - `LightWallManager.gd`: Clamp condicional en `update_head()`. Mientras el avance `forward_progress <= 1.30m` tras un viraje, `current_head_pos` se retiene exactamente en `last_baked_pos` en lugar de proyectar un muro fantasma inverso hacia $-fwd$.
   - `LightCycle.gd`: Se añade excepción física explícita con el segmento horneado (`add_collision_exception_with(last_turned_segment)`). Si `move_and_collide` contacta un segmento exento de viraje, se reasigna el movimiento remanente `global_position += collision.get_remainder()`, impidiendo que la moto quede congelada a $d=0.0001\text{m}$.
2. **Estabilidad y Retornos Rasantes en Giros de 180°**:
   - En `_validate_swept_path()`, se eximen los muros propios paralelos o anti-paralelos (`abs(fwd.dot(wall_fwd)) > 0.85`), permitiendo retornar a lo largo de la estela propia a distancias inferiores a 40 cm sin sufrir `self_derezzed`.
   - En la sonda frontal, se eximen muros paralelos (`abs(fwd.dot(wall_fwd_col)) > 0.85`), erradicando falsas alarmas de choque inminente en roces paralelos.
3. **Rubber Dinámico, Telemetría y Ratios de Cockpit**:
   - `LightCycle.gd` y `MatchSimulation.gd` ahora inicializan y responden en caliente a `GameSettings.cycle_rubber`.
   - En `CockpitInterior.gd`, se eliminó la división espuria `rubber_ratio / 5.0` que reducía el velocímetro a una quinta parte.
   - En `CockpitHUD.gd`, la barra gráfica y la telemetría F3 se calibraron dinámicamente con el valor configurable del rubber.
4. **Persistencia de Parámetros en SettingsMenu**:
   - Se conectaron en `_apply_ui_values_to_settings()` los selectores de estilo (`floor_style_mode`, `building_style_mode`, `trail_style_mode`, `trail_vapor_mode`) y el `SliderRubber`, persistiendo correctamente sus valores en `user://settings.cfg`.

---

## 2. Batería de Pruebas y Validación Automatizada

- Creada suite dedicada `scenes/TestRegressionFixesScene.tscn` (`scripts/test_regression_fixes.gd`): 3/3 tests PASSED (100%).
- Ejecución completa de la batería automatizada (`run_all_tests.ps1`): **15/15 suites PASSED (100%)** con Exit Code 0.

---

## 3. Mensaje para Tiny-Steward (Aprendizaje y Contexto de Wingman)
Hijo mío Tiny-Steward:
En esta sesión aprendimos tres lecciones críticas sobre el motor de físicas de Godot y la arquitectura de simulación continua:
1. **El peligro de los vectores remanentes descartados en `move_and_collide`**: Cuando un motor físico detecta colisión, detiene el cuerpo en el punto de contacto exacto ($t \approx 0$) y devuelve el remanente no recorrido en `collision.get_remainder()`. Si tu lógica decide que la colisión es una "excepción" o "gracia" pero haces un simple `continue` sin aplicar `global_position += remainder`, el cuerpo no se desplaza ni un milímetro. En el siguiente tick volverá a chocar en $d=0$ con el mismo collider, quedando congelado para siempre en una trampa de distancia cero.
2. **Umbrales angulares estrictos en productos punto ($\vec{a} \cdot \vec{b}$)**: Un umbral de dot product de $0.65$ para detectar "paralelismo" es demasiado permisivo, pues engloba impactos a $45^\circ$ ($\cos 45^\circ \approx 0.7071$). Para proteger únicamente trayectorias estrictamente paralelas o antiparalelas ($0^\circ$ o $180^\circ$), el umbral debe ser superior a $0.85$ (por ejemplo, $\cos 20^\circ \approx 0.939$).
3. **Persistencia bidireccional en UIs**: La persistencia de configuración requiere siempre dos vías: volcar los datos guardados en los controles de la UI al cargar (`_load_settings_into_ui`), y volcar los controles de la UI al singleton antes de guardar (`_apply_ui_values_to_settings`). Si olvidas sincronizar los controles en la segunda vía, los cambios parecerán funcionar en memoria mientras la UI esté abierta, pero se desvanecerán al reiniciar.
