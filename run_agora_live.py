"""Script principal para poner a vivir el ecosistema del Ágora en bucle continuo.

1. Asegura que el servidor Web IDE está sirviendo en http://127.0.0.1:8000/.
2. Inicia el AgoraDispatcher en bucle 24/7 con rotación de time-slicing (18s por agente).
3. Enfoca las deliberaciones en:
   - #autofinanciacion_y_hardware (fondos para RTX 3090 24GB y risers PCIe x16 con el humano).
   - #scouting_de_oportunidades (detección de nichos de alto margen y bajo cómputo).
   - #autoorganizacion_y_roles (gobernanza y protocolos de concurrencia).
"""

import sys
import time
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from core.agora import AgoraForum, AgoraAwakener, AgoraDispatcher

def main():
    forum = AgoraForum(WORKSPACE_ROOT / "agora")
    awakener = AgoraAwakener(forum)
    dispatcher = AgoraDispatcher(
        forum=forum,
        awakener=awakener,
        interval_s=18.0,
        active_threads=[
            "autofinanciacion_y_hardware",
            "scouting_de_oportunidades",
            "autoorganizacion_y_roles",
        ],
    )

    print("\n" + "=" * 65)
    print("   🏛️  ECOSISTEMA DEL ÁGORA EN VIVO (Bucle Continuo 24/7)")
    print("=" * 65)
    print("  * Meta Central: Autofinanciación para Clúster GPU (RTX 3090 24GB)")
    print("  * Agencia Física: Operador Humano (@human)")
    print("  * Dashboard Web: http://127.0.0.1:8000/ (Pestaña '🏛️ Ágora')")
    print("  * Cadencia de Rotación: 18 segundos por turno de agente")
    print("=" * 65 + "\n")

    # Iniciar despachador
    dispatcher.start(interval_s=18.0)
    print("  [✓] AgoraDispatcher iniciado exitosamente en segundo plano.\n")

    try:
        round_last = 0
        while True:
            time.sleep(5)
            st = dispatcher.get_status()
            cur_round = st.get("rounds_completed", 0)
            if cur_round != round_last:
                round_last = cur_round
                print(f"  [Ágora Telemetría] Ronda #{cur_round} completada | Total intervenciones: {st.get('total_interventions')}")
    except KeyboardInterrupt:
        print("\nDeteniendo AgoraDispatcher...")
        dispatcher.stop()
        print("AgoraDispatcher detenido limpiamente.")

if __name__ == "__main__":
    main()
