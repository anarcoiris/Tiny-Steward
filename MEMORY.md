# Long-Term Memory (Antigravity & Tiny Steward)

## Pulse Project (Flipper Killer Mk II)
- **Topología GND (2026-08-08)**: JLCPCB y KiCad son sensibles al *clearance*. Mantener el clearance del PCB en `0.12mm` es fundamental si se rutea en grillas de `0.125mm`. Es preferible aislar un solo pin lógico de GND al Flipper (Pin 8) para evitar Ground Loops que desestabilicen al ESP32.
- **Limitaciones de Autoruteo (Python A*)**: Los algoritmos ingenuos sin *Push & Shove* sufren de "atrapamiento" en PCBs denso (ej: Flipper 58x42mm). Para el 2-5% final, es más pragmático el ruteo asistido en KiCad o relajar los constraints de proximidad, antes que reescribir la heurística del A*.
- **Cálculo Trigonométrico Perimetral**: En el modelo de `BoardOutline`, se debe utilizar `math.cos(pi/4)` con 4 decimales mínimos `.4f` para ensamblar arcos (`gr_arc`) con líneas rectas y prevenir `[invalid_outline]` en KiCad DRC.

## Herramientas de JLCPCB
- El CSV (CPL) nativo de KiCad debe reescribirse a: `Designator, Mid X, Mid Y, Rotation, Layer`.
