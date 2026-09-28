# Antigravity Task Review: Cola Determinista de Acciones e Invarianza a Frame-Skipping

- **Fecha**: 2026-09-23
- **Proyecto**: Lightbikes (Godot 4.7.2)
- **Autor**: Antigravity (Wingman Agent)
- **Destinatario**: Tiny-Steward & Operator

---

## 1. Contexto y Problema Detectado
- Al producirse ráfagas de entrada (burst hotkeys) o al experimentar caídas momentáneas de fotogramas (frame-skipping del cliente), dos eventos de giro en la misma dirección se despachaban en el mismo frame instantáneo.
- Esto provocaba una singularidad geométrica de desplazamiento nulo ($\Delta d = 0$). Como LightWallManager exige $\ge 0.02\text{m}$ para hornear un segmento, el vértice intermedio se omitía y la moto se giraba 180° hacia atrás incrustada dentro de su propio muro emisor, provocando auto-bloqueo o falso self_derezzed.

---

## 2. Decisiones de Arquitectura e Implementación
1. **Despacho Post-Cinemático**: Se reubicó _process_turn_buffer() al paso 9 de _physics_process(), tras el movimiento y actualización de estela. Esto garantiza que entre virajes encadenados siempre exista desplazamiento real en el espacio 3D.
2. **Guardián de Ticks Físicos**: physics_ticks_since_last_turn en LightCycle.gd exige al menos 1 tick de integración física antes de despachar el siguiente giro en la misma dirección, encolando entradas excedentes en FIFO determinista.
3. **Excepción Nativa de Colisión**: Registro de dd_collision_exception_with(wall_manager.active_head_body) en setup_cycle().
4. **Nueva Suite de Pruebas**: Creada TestFrameSkippingAndQueueScene.tscn (3/3 PASS) y añadida a un_all_tests.ps1.

---

## 3. Estado de Pruebas
- **16/16 suites de prueba completadas con 100% de éxito (Exit Code 0)**.
- Invarianza determinista garantizada independientemente del framerate del cliente.
