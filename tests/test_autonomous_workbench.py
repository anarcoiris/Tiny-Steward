"""Pruebas Automatizadas del Banco de Trabajo Autónomo y la Deliberación de Intención.

Verifica la ejecución técnica individual por persona (CAD, finanzas, scouting, copy, auditoría),
la evaluación previa de intención (Lurk & Reflect vs Workbench vs Speak) y los endpoints REST.
"""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from core.agora import AgoraForum, AgoraAwakener, Persona, AgoraMessage
from core.memento import AgentMemento, evaluate_cognitive_intent, memento_manager
from core.workbench import AgentWorkbench, agent_workbench
from core.web_server import app


@pytest.fixture
def temp_workspace(tmp_path):
    w_dir = tmp_path / "workspace"
    w_dir.mkdir()
    return w_dir


def test_workbench_execution_all_personas(temp_workspace):
    wb = AgentWorkbench(workspace_root=temp_workspace)

    # 1. 🦊 Craft-Fox
    res_fox = wb.execute_autonomous_step("craft_fox")
    assert res_fox.status == "TASK_COMPLETED"
    assert res_fox.persona_id == "craft_fox"
    assert res_fox.deliverable_ready is True
    scad_file = temp_workspace / "fabrica" / "products" / "05_astronomia_optica" / "cheshire_collimator.scad"
    assert scad_file.exists()
    assert "cheshire_body" in scad_file.read_text(encoding="utf-8")

    # 2. 🐆 Quant-Lynx
    res_lynx = wb.execute_autonomous_step("quant_lynx")
    assert res_lynx.status == "TASK_COMPLETED"
    assert res_lynx.persona_id == "quant_lynx"
    margins_file = temp_workspace / "fabrica" / "finance" / "unit_margins_report.json"
    assert margins_file.exists()
    margins_data = json.loads(margins_file.read_text(encoding="utf-8"))
    assert "cheshire_collimator_1_25" in margins_data["products"]
    assert margins_data["products"]["cheshire_collimator_1_25"]["net_margin_percent"] > 70.0

    # 3. 🦉 Whisper-Owl
    res_owl = wb.execute_autonomous_step("whisper_owl")
    assert res_owl.status == "TASK_COMPLETED"
    radar_file = temp_workspace / "fabrica" / "scouting" / "wallapop_niche_report.json"
    assert radar_file.exists()
    radar_data = json.loads(radar_file.read_text(encoding="utf-8"))
    assert len(radar_data["market_observations"]) >= 2

    # 4. 🦅 Signal-Raven
    res_raven = wb.execute_autonomous_step("signal_raven")
    assert res_raven.status == "TASK_COMPLETED"
    listing_file = temp_workspace / "fabrica" / "channels" / "wallapop" / "cheshire_collimator_listing.md"
    assert listing_file.exists()
    assert "Colimador Cheshire" in listing_file.read_text(encoding="utf-8")

    # 5. 🐱 Tiny-Steward
    res_master = wb.execute_autonomous_step("tiny_steward")
    assert res_master.status == "TASK_COMPLETED"
    cert_file = temp_workspace / "fabrica" / "products" / "verification_certificate.json"
    assert cert_file.exists()
    cert_data = json.loads(cert_file.read_text(encoding="utf-8"))
    assert cert_data["verdict"] == "APPROVED_FOR_AUTOFINANCING"
    assert len(cert_data["audited_artifacts"]) >= 3


def test_deliberative_intent_evaluation():
    memento = AgentMemento(
        persona_id="craft_fox",
        workbench_task={"title": "Modelado CAD", "status": "IN_PROGRESS"},
    )

    # Caso 1: Mención directa -> DEBE HABLAR
    dec1 = evaluate_cognitive_intent(
        persona_id="craft_fox",
        thread_slug="debate_general",
        recent_messages=[],
        memento=memento,
        is_mentioned=True,
    )
    assert dec1.action == "SPEAK"
    assert "mención directa" in dec1.reasoning.lower()

    # Caso 2: Sin mención y con tarea en taller -> DEBE TRABAJAR (WORKBENCH)
    dec2 = evaluate_cognitive_intent(
        persona_id="craft_fox",
        thread_slug="debate_general",
        recent_messages=[],
        memento=memento,
        is_mentioned=False,
    )
    assert dec2.action == "WORKBENCH"
    assert "taller" in dec2.reasoning.lower() or "banco" in dec2.reasoning.lower()

    # Caso 3: Hilo consolidado/cerrado -> NO DEBE HABLAR EN PÚBLICO
    dec3 = evaluate_cognitive_intent(
        persona_id="craft_fox",
        thread_slug="debate_cerrado",
        recent_messages=[],
        memento=memento,
        is_consolidated=True,
    )
    assert dec3.action in ["WORKBENCH", "REFLECT_ONLY"]

    # Caso 4: El autor del último mensaje es el mismo agente -> NO HACER ECO DE LORO
    fake_msg = {"author_id": "craft_fox", "content": "Hola"}
    dec4 = evaluate_cognitive_intent(
        persona_id="craft_fox",
        thread_slug="debate_general",
        recent_messages=[fake_msg],
        memento=memento,
        is_mentioned=False,
    )
    assert dec4.action in ["WORKBENCH", "REFLECT_ONLY"]
    assert "mía" in dec4.reasoning.lower()


def test_workbench_web_api_endpoints():
    client = TestClient(app)

    # 1. GET Workbench de Craft-Fox
    resp = client.get("/api/agora/personas/craft_fox/workbench")
    assert resp.status_code == 200
    data = resp.json()
    assert data["persona_id"] == "craft_fox"
    assert "personal_goals" in data
    assert "workbench_task" in data
    assert len(data["personal_goals"]) >= 2

    # 2. POST Disparar paso en banco de trabajo
    resp_step = client.post("/api/agora/personas/craft_fox/workbench/step")
    assert resp_step.status_code == 200
    step_data = resp_step.json()
    assert step_data["status"] == "ok"
    assert step_data["result"]["status"] in ["STEP_COMPLETED", "TASK_COMPLETED"]

    # 3. POST Añadir objetivo personal
    new_goal = "Optimizar ángulo de desmoldeo para sellos botánicos a 7 grados."
    resp_goal = client.post(
        "/api/agora/personas/craft_fox/goals",
        json={"goal": new_goal},
    )
    assert resp_goal.status_code == 200
    assert new_goal in resp_goal.json()["personal_goals"]

    # 4. DELETE Eliminar objetivo personal
    idx = len(resp_goal.json()["personal_goals"]) - 1
    resp_del = client.delete(f"/api/agora/personas/craft_fox/goals/{idx}")
    assert resp_del.status_code == 200
    assert new_goal not in resp_del.json()["personal_goals"]
