# Antigravity Task Review: Blindaje Anti-Atravesamiento, Modelos y Reflexiones SSR

- **Fecha**: 2026-09-23
- **Proyecto**: Lightbikes (Godot 4.7.2)
- **Autor**: Antigravity (Wingman Agent)
- **Destinatario**: Tiny-Steward & Operator

---

## 1. Problemas Abordados y Diagnóstico
1. **Atravesamiento de Muros**: La condición bsf(cycle_fwd.dot(own_fwd)) > 0.85 en _validate_swept_path() permitía cortar el plano de muros propios sin muerte.
2. **Duplicación de Piloto y Cockpit en Bots**: ase_basic_pbr_optimized.glb ya tiene el piloto modelado en su malla (31k vértices en  > 0.5\text{m}$). Al instanciar ProceduralCyberRider, aparecían dos pilotos superpuestos. En bots, CockpitCamera.deactivate() dejaba la cabina flotante visible.
3. **Reflexión de Muros en Suelo**: Los shaders de estela usaban lend_mix (pase transparente), por lo que SSR en el suelo opaco no los capturaba.

---

## 2. Solución Aplicada
1. Eliminado el bypass de swept-ray: cualquier corte transversal fuera de 1.8m es letal (self_derezzed).
2. Sincronizada visibilidad de RiderController: apagado en modo Cyber GLB y activo solo en modo Retro. Ocultados cockpit_mesh y cockpit_interior en deactivate().
3. Shaders de estela configurados con ALPHA_SCISSOR_THRESHOLD = 0.05 y depth_draw_always para participar en el pase opaco de SSR.
4. Creada suite TestWallCrossingAndModelCleanupScene.tscn (4/4 PASS).

---

## 3. Estado de Pruebas
- **17/17 suites de prueba pasadas al 100%** en un_all_tests.ps1 (Exit Code 0).
