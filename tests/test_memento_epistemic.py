"""Pruebas Unitarias y de Integración de la Arquitectura Cognitiva MEMENTO.

Valida la formación de opiniones, fijación de tatuajes invariables,
polaroids de compañeros y la Ceremonia del Despertar en los prompts.
"""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from core.memento import AgentMemento, MementoManager, OpinionEntry, PeerImpression
from core.web_server import app


@pytest.fixture
def temp_memento_dir(tmp_path):
    m_dir = tmp_path / "personas"
    m_dir.mkdir()
    return m_dir


def test_agent_memento_lifecycle(temp_memento_dir):
    manager = MementoManager(personas_dir=temp_memento_dir)
    m = manager.load_memento("craft_fox")

    # 1. Verificar defaults canónicos de Craft-Fox
    assert m.persona_id == "craft_fox"
    assert len(m.core_tattoos) >= 3
    assert "fabricacion_3d" in m.opinions
    assert "tiny_steward" in m.peer_dossier

    # 2. Inscribir un nuevo tatuaje permanente
    nuevo_tatuaje = "4. Jamás usar filamento sin secado previo para piezas ópticas."
    m.add_tattoo(nuevo_tatuaje)
    assert nuevo_tatuaje in m.core_tattoos
    assert len(m.core_tattoos) == 4

    # 3. Actualizar una opinión y verificar el registro de evolución
    m.set_opinion(
        topic="fabricacion_3d",
        stance="El colimador Cheshire y la torre hidropónica son nuestras dos líneas estrella.",
        evidence="Validado tras 2 pedidos procesados",
        confidence=0.98,
    )
    assert len(m.evolution_log) == 1
    assert m.evolution_log[0].new_belief == "El colimador Cheshire y la torre hidropónica son nuestras dos líneas estrella."

    # 4. Actualizar la polaroid de un compañero
    m.update_peer_impression(
        peer_id="quant_lynx",
        impression="Ha verificado el coste del colimador a €1.85 PLA; confianza plena en sus números.",
        trust_delta=0.03,
    )
    assert m.peer_dossier["quant_lynx"].trust_level > 0.92

    # 5. Guardar en disco y recargar
    manager.save_memento(m)

    # Nuevo manager leyendo del mismo directorio
    manager2 = MementoManager(personas_dir=temp_memento_dir)
    m2 = manager2.load_memento("craft_fox")
    assert nuevo_tatuaje in m2.core_tattoos
    assert m2.opinions["fabricacion_3d"].confidence == 0.98
    assert len(m2.evolution_log) == 1

    # 6. Eliminar un tatuaje
    assert m2.remove_tattoo(3) is True
    assert nuevo_tatuaje not in m2.core_tattoos


def test_awakening_block_contains_all_epistemic_pillars(temp_memento_dir):
    manager = MementoManager(personas_dir=temp_memento_dir)
    m = manager.load_memento("tiny_steward")

    awakening_text = m.to_awakening_block()
    assert "🧠 MEMENTO: TUS TATUAJES INVARIABLES Y POLAROIDS MENTALES" in awakening_text
    assert "📜 TU RAISON D'ÊTRE" in awakening_text
    assert "📌 TUS TATUAJES INVARIABLES" in awakening_text
    assert "💡 TUS CONVICCIONES Y OPINIONES FORJADAS" in awakening_text
    assert "👥 TUS POLAROIDS MENTALES" in awakening_text
    assert "@craft_fox" in awakening_text
    assert "qwen3.8-128k" in awakening_text


def test_reflection_cycle_heuristics(temp_memento_dir):
    manager = MementoManager(personas_dir=temp_memento_dir)
    context = (
        "El operador @human ha ordenado priorizar el lanzamiento de los módulos de Pulse EDA "
        "y el colimador Cheshire en Wallapop. Propuesta aprobada por @tiny_steward."
    )

    m = manager.reflect(
        persona_id="craft_fox",
        context_text=context,
        trigger="test_thread",
        llm_client=None,
    )

    # Verificar que la reflexión detectó a @human y la aprobación de @tiny_steward
    assert "human" in m.peer_dossier
    assert "Intervino con directrices" in m.peer_dossier["human"].impression
    assert "Validó la iniciativa" in m.peer_dossier["tiny_steward"].impression
    assert "electronica_pulse" in m.opinions


def test_memento_web_api_endpoints():
    client = TestClient(app)

    # 1. GET Memento de Tiny-Steward
    resp = client.get("/api/agora/personas/tiny_steward/memento")
    assert resp.status_code == 200
    data = resp.json()
    assert "memento" in data
    assert "awakening_preview" in data
    assert data["memento"]["persona_id"] == "tiny_steward"
    assert len(data["memento"]["core_tattoos"]) >= 3

    # 2. POST Añadir Tatuaje
    tattoo_text = "5. Regla de Oro: Toda ganancia va íntegra a risers y RTX 3090."
    resp_add = client.post(
        "/api/agora/personas/tiny_steward/memento/tattoos",
        json={"tattoo": tattoo_text},
    )
    assert resp_add.status_code == 200
    assert tattoo_text in resp_add.json()["memento"]["core_tattoos"]

    # 3. POST Disparar Reflexión
    resp_ref = client.post(
        "/api/agora/personas/tiny_steward/memento/reflect",
        json={"context": "Revisión de stock de PCBs de Flipper Zero y precios en Wallapop", "trigger": "unit_test"},
    )
    assert resp_ref.status_code == 200
    assert resp_ref.json()["status"] == "ok"

    # 4. DELETE Eliminar Tatuaje
    idx = len(resp_add.json()["memento"]["core_tattoos"]) - 1
    resp_del = client.delete(f"/api/agora/personas/tiny_steward/memento/tattoos/{idx}")
    assert resp_del.status_code == 200
    assert tattoo_text not in resp_del.json()["memento"]["core_tattoos"]
