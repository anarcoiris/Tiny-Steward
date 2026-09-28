"""Limpieza profunda y des-duplicación real de todos los hilos del Ágora.
Elimina repeticiones idénticas preservando la progresión histórica y los mensajes del humano.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Añadir workspace a sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.agora import AgoraForum

forum = AgoraForum()
threads = forum.list_threads()

for t in threads:
    slug = t.slug
    thread_file = forum.get_thread_file(slug)
    if not thread_file.exists():
        continue

    lines = [json.loads(l) for l in thread_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not lines:
        continue

    initial_len = len(lines)
    cleaned = []
    seen_hashes = set()

    for m in lines:
        author = m.get("author_id", "")
        content = (m.get("content") or "").strip()
        # Clave semántica: autor + primeros 120 caracteres del mensaje
        key = f"{author}:{content[:120]}"

        # Los mensajes del humano siempre se conservan
        if author == "human":
            cleaned.append(m)
            continue

        if key in seen_hashes:
            continue

        seen_hashes.add(key)
        cleaned.append(m)

    # Sobrescribir archivo limpio
    with open(thread_file, "w", encoding="utf-8") as f:
        for m in cleaned:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    forum.render_markdown(slug)
    print(f"[OK] #{slug}: {initial_len} -> {len(cleaned)} mensajes limpios.")
