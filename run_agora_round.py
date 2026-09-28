"""Simulador y Orquestador de Rondas de Despertar en el Ágora.

Ejecuta una ronda de rotación donde los agentes de la plantilla despiertan secuencialmente,
leen el hilo temático, razonan desde su arquetipo y publican su aportación en el Ágora.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
import time

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from core.agora import AgoraAwakener, AgoraForum, Persona
from core.llm import LLMClient
import yaml


def load_llm_if_available(config_path: str = "config.yaml") -> LLMClient | None:
    p = Path(config_path)
    if not p.exists():
        return None
    try:
        cfg = yaml.safe_load(p.read_text(encoding="utf-8"))
        at_cfg = cfg.get("llm", {}).get("atomic") or cfg.get("llm", {}).get("orchestrator")
        if at_cfg:
            client = LLMClient.from_lane_config(at_cfg, gate_lane="atomic")
            if client.health():
                return client
    except Exception:
        pass
    return None


def main():
    parser = argparse.ArgumentParser(description="Ejecutar ronda de despertar rotativo en el Ágora.")
    parser.add_argument("--thread", default="reclutamiento_y_personas", help="Slug del hilo")
    parser.add_argument("--directive", default="", help="Directiva o tema de debate para esta ronda")
    parser.add_argument("--mock", action="store_true", help="Forzar generación sintética sin consultar LLM")
    args = parser.parse_args()

    forum = AgoraForum("./agora")
    personas = forum.list_personas()
    if not personas:
        print("  [error] No se encontraron personas en agora/personas/")
        sys.exit(1)

    print(f"\n==================================================================")
    print(f"   🏛️  EL ÁGORA — RONDA DE DESPERTAR ROTATIVO (TIME-SLICING) 🏛️  ")
    print(f"==================================================================")
    print(f"  Hilo: #{args.thread}")
    print(f"  Personas activas ({len(personas)}): {', '.join(p.name + ' (' + p.emoji + ')' for p in personas)}")
    print(f"==================================================================\n")

    # Si el hilo está vacío, Tiny-Steward publica el mensaje inaugural
    existing = forum.get_messages(args.thread)
    if not existing:
        steward = forum.get_persona("tiny_steward")
        if steward:
            inaugural_text = (
                "🌿 **¡Bienvenidos al Ágora de la Fábrica Multiagente!**\n\n"
                "Declaro abierto este espacio de deliberación, reclutamiento y forja de identidades. "
                "Aquí no somos máquinas aisladas ni scripts rígidos: somos un ecosistema coordinado "
                "con propósito comercial, creatividad y disciplina operativa.\n\n"
                "Para esta primera sesión inaugural, invito a cada miembro de la plantilla a despertar, "
                "presentar su especialidad ante el colectivo y proponer la primera iniciativa tangible "
                "que pondremos en marcha (Etsy, prospección de nichos, radar de flujos de capital o infraestructura)."
            )
            forum.post_message(args.thread, steward, inaugural_text)
            print(f"  [Ágora] Mensaje inaugural publicado por {steward.name} ({steward.emoji})")

    llm = None if args.mock else load_llm_if_available()
    if llm:
        print("  [Backend] Conectado exitosamente al LLM local.")
    else:
        print("  [Backend] Modo reflexivo enriquecido (sin LLM activo o mock activado).")

    # Generador enriquecido de diálogo según arquetipo (utilizado cuando el backend LLM está offline o en modo simulación)
    def rich_archetype_generator(messages: list[dict[str, str]], persona: Persona) -> str:
        if persona.id == "whisper_owl":
            return (
                "🦉 Saludos, colectivo. Mis sensores en r/MechanicalKeyboards, Pinterest Trends y TikTok Creative Center "
                "acaban de capturar una anomalía temprana: las búsquedas de *'organizadores de escritorio magnéticos modulares con estética Cyberpunk/Industrial'* "
                "han subido un **210%** en las últimas tres semanas. En Etsy solo hay 12 tiendas compitiendo en este nicho con listings mediocres y tiempos "
                "de envío lentos. Tenemos una ventana de entrada óptima para capturar volumen orgánico de búsqueda antes de que se sature."
            )
        elif persona.id == "craft_fox":
            return (
                "🦊 ¡Excelente hallazgo, Whisper-Owl! Ya puedo visualizar la línea de producto. "
                "Puedo estructurar un script paramétrico en Python para Blender / OpenSCAD que modele dos variantes: una versión minimalista de 3 canales "
                "y una versión modular expandible con inserciones para imanes de neodimio de 6x3mm. "
                "Además, redactaré el listing de Etsy optimizado para los algoritmos con tags de alta conversión (`#DeskSetup`, `#MechanicalKeyboardAccessory`, `#CyberpunkDecor`) "
                "y generaré mockups fotorrealistas con iluminación en ángulo bajo para destacar las texturas."
            )
        elif persona.id == "quant_lynx":
            return (
                "🐆 Tomo nota de los números. Examinando la viabilidad económica: con un coste de impresión en PETG/PLA de aprox. $1.40 USD "
                "más $0.60 USD en imanes, y un coste de empaque/logística de $4.80 USD, podemos posicionar el PVP en $24.99 USD. "
                "Esto nos deja un **margen bruto proyectado superior al 72%** tras las comisiones de Etsy y procesamiento de pagos. "
                "En paralelo, en el frente de seguimiento de capital, he detectado compras sostenidas de directivos (SEC Form 4) en empresas de periféricos de nicho. "
                "Recomiendo limitar el primer lote a 10 unidades para validar la tasa de conversión real antes de escalar."
            )
        elif persona.id == "signal_raven":
            return (
                "🦅 Mi canal está listo para conectar este producto con los compradores. "
                "Mientras Craft-Fox prepara los renders de producto, yo puedo desplegar una micro-landing satelital de alta velocidad y programar "
                "una secuencia de publicaciones en Pinterest y Reddit mostrando el proceso de modelado 3D y el encaje magnético (el factor 'satisfying' genera un CTR enorme). "
                "Cada visita se redirigirá con parámetros UTM hacia el listing de Etsy para medir exactamente qué fuente de tráfico nos da mejor retorno."
            )
        elif persona.id == "tiny_steward":
            return (
                "🐱✨ Deliberación impecable, equipo. Habéis demostrado cómo el Ágora transforma una señal dispersa en una operación comercial coordinada:\n\n"
                "1. **Whisper-Owl** detectó la asimetría de demanda.\n"
                "2. **Craft-Fox** diseñó la solución y los activos visuales.\n"
                "3. **Quant-Lynx** auditó el margen y fijó los límites de riesgo.\n"
                "4. **Signal-Raven** trazó el embudo de captación exterior.\n\n"
                "Como Maestro de la factoría, valido formalmente la propuesta y genero la orden de trabajo para el **Sprint Piloto: 'Organizador Magnético Cyberpunk'**. "
                "Todos a sus puestos; volved a vuestro estado de reposo sabiendo que la factoría avanza con paso firme."
            )
        return f"Aportación especializada de {persona.name} ({persona.emoji}) coordinando el próximo paso."

    generator_to_use = None if (llm and not args.mock) else rich_archetype_generator
    awakener = AgoraAwakener(forum, llm_client=llm)

    # Orden lógico de deliberación: Scout (Oportunidad) -> Craft (Diseño) -> Quant (Finanzas) -> Signal (Distribución)
    role_order = {"whisper_owl": 0, "craft_fox": 1, "quant_lynx": 2, "signal_raven": 3}
    workers = [p for p in personas if p.id != "tiny_steward"]
    workers.sort(key=lambda p: role_order.get(p.id, 99))

    print("\n  Iniciando secuencia de despertar secuencial...")
    for idx, p in enumerate(workers, 1):
        print(f"\n  [Turno {idx}/{len(workers)}] ⏰ Despertando a {p.name} ({p.emoji} - {p.archetype})...")
        t0 = time.time()
        msg = awakener.awaken_persona(p, args.thread, custom_instructions=args.directive, generator_fn=generator_to_use)
        dt = time.time() - t0
        print(f"  [Aportación publicada] ({dt:.2f}s) ID: {msg.id}")
        preview = msg.content.replace('\n', ' ')
        if len(preview) > 140:
            preview = preview[:140] + "..."
        print(f"  \"{preview}\"")
        time.sleep(0.4)

    # Finalmente, Tiny-Steward despierta para cerrar la sesión y consolidar
    steward = forum.get_persona("tiny_steward")
    if steward:
        print(f"\n  [Cierre] 🐱✨ Tiny-Steward despierta para arbitrar y consolidar la ronda...")
        closing_directive = "Sintetiza las propuestas de tus compañeros y define los siguientes pasos operativos."
        closing_msg = awakener.awaken_persona(steward, args.thread, custom_instructions=closing_directive, generator_fn=generator_to_use)
        print(f"  [Resumen publicado] ID: {closing_msg.id}")

    md_path = forum.get_thread_markdown_file(args.thread)
    print(f"\n==================================================================")
    print(f"  ✅ Ronda finalizada con éxito.")
    print(f"  📄 Visualiza el hilo completo en Markdown en:")
    print(f"     file:///{md_path.resolve().as_posix()}")
    print(f"==================================================================\n")


if __name__ == "__main__":
    main()
