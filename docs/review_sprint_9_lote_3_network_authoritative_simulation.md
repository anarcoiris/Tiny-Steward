# Revisión Sprint 9 — Lote 3: Red Multijugador y Simulación Autoritativa

## 1. Resumen Ejecutivo
- **Objetivo**: Sincronizar constantes físicas en el motor autoritativo de red (MatchSimulation.gd), blindar la seguridad RPC (ArenaManager.gd, NetworkManager.gd) y desacoplar rutas absolutas fijas en LightCycle.gd.
- **Estado**: ✅ COMPLETADO Y VERIFICADO AL 100% (20/20 Suites en verde).

## 2. Bugs Resueltos en Lote 3
- **BUG-06 (Centralización de Constantes Físicas)**: Sincronización canónica estricta entre MatchSimulation.gd y LightCycle.gd (BASE_CRUISE_SPEED = 34.0, MIN_SPEED = 18.0, MAX_THROTTLE_SPEED = 52.0, MAX_GRIND_SPEED = 90.0, MAX_HYPER_SPEED = 105.0, ACCEL_RATE = 45.0). Se eliminó la divergencia de velocidades de crucero y aceleración en la simulación autoritativa a 120 Hz.
- **BUG-17 / BUG-32 (Blindaje y Autoridad @rpc)**: Adición de @rpc("authority") y validación de sender_id (servidor/peer 1) en ArenaManager.rpc_restart_round(), NetworkManager.sync_player_list(), NetworkManager.rpc_start_match(), y NetworkManager.rpc_return_to_lobby(). Previene inyecciones de comandos no autorizados o reseteo forzado de partidas por parte de clientes maliciosos.
- **BUG-31 (Desacoplamiento de Rutas /root/MainArena)**: Sustitución de rutas absolutas duras en LightCycle.gd (L1379, 1574, 1636) por resolución dinámica a través de grupos del SceneTree (match_director, ffects_container) con fallback seguro. Permite ejecutar ciclos en arenas personalizadas y suites de test aisladas.

## 3. Suite de Pruebas Automatizadas
- Suite: scenes/tests/TestBatch3NetworkScene.tscn / scripts/tests/test_batch3_network.gd.
- 3/3 pruebas superadas sin excepciones ni fugas de ObjectDB.
- Integrado en un_all_tests.ps1 (20/20 suites en verde).
