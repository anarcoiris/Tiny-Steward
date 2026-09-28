# Revisión Sprint 9 — Lote 2: Cámaras Cinematográficas y Estabilidad Visual

## 1. Resumen Ejecutivo
- **Objetivo**: Resolver las discrepancias visuales, sacudidas y anomalías de control de cámara en SpectatorCamera.gd y CockpitCamera.gd.
- **Estado**: ✅ COMPLETADO Y VERIFICADO AL 100% (19/19 Suites en verde).

## 2. Bugs Resueltos en Lote 2
- **BUG-21 (SpectatorCamera Teleport en Curva)**: Se corrigió el salto abrupto de posición (~1.67m) producido por el offset rígido ront_wheel_offset al realizar virajes ortogonales de 90°. Se implementó smoothed_fwd_offset con decaimiento elástico exponencial (1.0 - exp(-12.0 * delta)) y modulación de amortiguación posicional (pos_decay = 8.0 durante giros bruscos ngle_diff > 0.35).
- **BUG-22 (SpectatorCamera Null Safety & Modos Huérfanos)**: Blindaje total con guardas is_instance_valid(current_target) en _process_panoramic_climb(), _process_panoramic_chase(), _get_spectator_speed_factor() y _on_cycle_crashed() cuando los ciclos caen o se liberan de memoria.
- **BUG-29 (CockpitCamera Aislamiento de Ratón en Pantalla Dividida)**: Se restringió la captura del ratón (capture_mouse) y el procesamiento de eventos en _input() a player_index == 0. Los jugadores 1..3 en Split-Screen quedan completamente desacoplados del puntero global del sistema operativo.
- **BUG-34 (CockpitCamera Suavizado Sub-Tick de Render)**: Se desacopló la posición de cámara de la frecuencia física (120 Hz) mediante smoothed_parent_pos con interpolación sub-tick continua (pos_decay = 45.0), eliminando micro-stuttering en pantallas de 144Hz / 240Hz y giros discretos.

## 3. Suite de Pruebas Automatizadas
- Suite: scenes/tests/TestBatch2CamerasScene.tscn / scripts/tests/test_batch2_cameras.gd.
- 4/4 pruebas unitarias superadas con 0 fugas de ObjectDB.
- Integrado en un_all_tests.ps1 (19/19 suites exitosas).
