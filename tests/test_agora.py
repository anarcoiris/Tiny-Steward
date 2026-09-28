"""Tests unitarios para el sistema del Ágora, Personas y Despertar Rotativo."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from core.agora import (
    AgoraAwakener,
    AgoraForum,
    AgoraMessage,
    AgoraThread,
    Persona,
)


@pytest.fixture
def temp_agora(tmp_path: Path) -> AgoraForum:
    return AgoraForum(base_dir=tmp_path / "agora")


def test_persona_creation_and_persistence(tmp_path: Path):
    persona_path = tmp_path / "persona_test.json"
    p = Persona(
        id="test_bot",
        name="TestBot",
        archetype="El Evaluador",
        emoji="🔬",
        focus_areas=["Testing", "Auditoría"],
        system_prompt="Eres un bot de pruebas.",
        temperature=0.5,
    )
    p.add_journal_entry("Iniciando test de persona.")
    p.save(persona_path)

    loaded = Persona.load(persona_path)
    assert loaded.id == "test_bot"
    assert loaded.name == "TestBot"
    assert loaded.emoji == "🔬"
    assert len(loaded.life_journal) == 1
    assert "Iniciando test" in loaded.life_journal[0]["entry"]


def test_agora_forum_threads_and_messages(temp_agora: AgoraForum):
    author = Persona(
        id="owl",
        name="Whisper-Owl",
        archetype="Scout",
        emoji="🦉",
    )
    msg1 = temp_agora.post_message(
        "reclutamiento",
        author,
        "¡Hola a todos! He llegado al Ágora.",
    )
    assert msg1.id.startswith("msg_")
    assert msg1.author_id == "owl"

    msg2 = temp_agora.post_message(
        "reclutamiento",
        {"id": "fox", "name": "Craft-Fox", "emoji": "🦊"},
        "¡Saludos Owl! Listo para construir.",
        in_reply_to=msg1.id,
        proposal={"action": "crear_producto", "item": "soporte_soldador"},
    )
    assert msg2.in_reply_to == msg1.id
    assert msg2.proposal["item"] == "soporte_soldador"

    # Verificar mensajes en el hilo
    messages = temp_agora.get_messages("reclutamiento")
    assert len(messages) == 2
    assert messages[0].content == "¡Hola a todos! He llegado al Ágora."
    assert messages[1].author_name == "Craft-Fox"

    # Verificar renderizado de Markdown
    md_file = temp_agora.get_thread_markdown_file("reclutamiento")
    assert md_file.exists()
    content = md_file.read_text(encoding="utf-8")
    assert "# 🏛️ Ágora de la Fábrica — Hilo: Reclutamiento" in content
    assert "Craft-Fox" in content
    assert "soporte_soldador" in content


def test_agora_awakening_round(temp_agora: AgoraForum):
    p1 = Persona(id="owl", name="Whisper-Owl", archetype="Scout", emoji="🦉")
    p2 = Persona(id="fox", name="Craft-Fox", archetype="Artesano", emoji="🦊")
    temp_agora.save_persona(p1)
    temp_agora.save_persona(p2)

    awakener = AgoraAwakener(temp_agora)

    # Inyectamos una función generadora simulada
    def mock_generator(messages: list[dict[str, str]], persona: Persona) -> str:
        return f"Aportación reflexiva de {persona.name} ({persona.emoji}) sobre el hilo."

    results = awakener.run_awakening_round(
        "ideas_productos",
        personas=[p1, p2],
        generator_fn=mock_generator,
        delay_between_s=0.0,
    )

    assert len(results) == 2
    assert results[0].author_name == "Whisper-Owl"
    assert "Whisper-Owl" in results[0].content
    assert results[1].author_name == "Craft-Fox"
    assert "Craft-Fox" in results[1].content

    # Verificar que el diario de vida se actualizó
    loaded_p1 = temp_agora.get_persona("owl")
    assert loaded_p1 is not None
    assert len(loaded_p1.life_journal) >= 1


def test_persona_skill_domains_resolution():
    from core.skill_loader import Skill, SkillIndex, resolve_persona_skills

    skills = [
        Skill(name="Threat Intel Tool", slug="threat_intel_tool", path="threat_intelligence/osint.md", tags=["threat_intelligence", "osint"]),
        Skill(name="CAD 3D Tool", slug="cad_3d_tool", path="ecommerce/cad.md", tags=["ecommerce", "3d"]),
        Skill(name="Policy Compliance", slug="policy_compliance", path="compliance_and_grc/auditing.md", tags=["compliance_and_grc"]),
    ]
    index = SkillIndex(skills)

    owl = Persona(id="owl", name="Owl", archetype="Scout", assigned_skill_domains=["threat_intelligence"])
    resolved = resolve_persona_skills(owl, index)
    assert len(resolved) == 1
    assert resolved[0].slug == "threat_intel_tool"

    fox = Persona(id="fox", name="Fox", archetype="Craft", assigned_skill_domains=["ecommerce"])
    resolved_fox = resolve_persona_skills(fox, index)
    assert len(resolved_fox) == 1
    assert resolved_fox[0].slug == "cad_3d_tool"


def test_worker_evaluations_and_master_steering(temp_agora: AgoraForum):
    # Verify default scorecard initialization
    evals = temp_agora.get_worker_evaluations()
    assert "whisper_owl" in evals
    assert "craft_fox" in evals
    assert evals["whisper_owl"]["score"] >= 90

    # Master evaluates worker with feedback and new focus
    updated = temp_agora.evaluate_worker(
        worker_id="craft_fox",
        evaluator_id="tiny_steward",
        score=92,
        rating="A",
        feedback="Excelente cambio a paquetes STL digitales puros.",
        current_focus="Modelado paramétrico de carcasas PCB.",
    )
    assert updated["score"] == 92
    assert updated["rating"] == "A"
    assert updated["current_focus"] == "Modelado paramétrico de carcasas PCB."

    # Verify persistence
    evals_reload = temp_agora.get_worker_evaluations()
    assert evals_reload["craft_fox"]["score"] == 92


def test_mission_propose_steer_approve(temp_agora: AgoraForum):
    # Worker proposes mission
    prop = temp_agora.propose_mission(
        thread_slug="autofinanciacion_y_hardware",
        proposer_id="whisper_owl",
        mission_data={
            "title": "Auditorías DevSecOps Rápidas",
            "target_revenue_eur": 450,
            "pricing_eur": 45,
            "deliverables": ["Reporte PDF", "Checklist SBOM"],
            "payment_channels": ["BTC", "XMR"],
        },
    )
    assert prop["id"].startswith("mission_")
    assert prop["status"] == "pending_review"

    # Master steers mission
    steering = temp_agora.steer_mission(
        thread_slug="autofinanciacion_y_hardware",
        mission_id=prop["id"],
        steerer_id="tiny_steward",
        feedback="Limitar inferencia a 3 minutos para no recalentar GPUs.",
        required_changes=["Tiempo máx 3 min", "Reporte directo en Markdown"],
    )
    assert steering["status"] == "steered"
    assert len(steering["required_changes"]) == 2

    # Master approves mission
    approval = temp_agora.approve_mission(
        thread_slug="autofinanciacion_y_hardware",
        mission_id=prop["id"],
        approver_id="tiny_steward",
        comments="Aprobado tras verificar límite térmico.",
    )
    assert approval["status"] == "approved_by_master"

    # Verify messages and markdown rendering
    messages = temp_agora.get_messages("autofinanciacion_y_hardware")
    assert len(messages) == 3
    # Check that original proposal message was updated to approved_by_master
    assert messages[0].proposal["status"] == "approved_by_master"
    assert messages[0].proposal.get("approved_by") == "tiny_steward"

    md_file = temp_agora.get_thread_markdown_file("autofinanciacion_y_hardware")
    md_text = md_file.read_text(encoding="utf-8")
    assert "Misión Comercial" in md_text
    assert "Directiva de Steering Maestra" in md_text
    assert "Aprobación Oficial" in md_text


def test_agora_silence_and_repose(temp_agora: AgoraForum):
    p1 = Persona(id="owl", name="Whisper-Owl", archetype="Scout", emoji="🦉")
    temp_agora.save_persona(p1)
    awakener = AgoraAwakener(temp_agora)

    events_received = []
    temp_agora.add_listener(lambda ev: events_received.append(ev))

    # 1. Generator returning explicit [SILENCIO]
    def silence_gen(msgs, persona):
        return "[SILENCIO]"

    res = awakener.awaken_persona(p1, "ideas_productos", generator_fn=silence_gen)
    assert res is None

    # No new message was posted
    msgs = temp_agora.get_messages("ideas_productos")
    assert len(msgs) == 0

    # Event agent_in_repose was emitted
    repose_events = [e for e in events_received if e["type"] == "agent_in_repose"]
    assert len(repose_events) == 1
    assert repose_events[0]["data"]["persona_id"] == "owl"

    # Persona journal recorded operational repose
    loaded_p1 = temp_agora.get_persona("owl")
    assert any("reposo" in entry["entry"] for entry in loaded_p1.life_journal)


def test_cognitive_engine_autoorganizacion_silence(temp_agora: AgoraForum):
    p1 = Persona(id="whisper_owl", name="Whisper-Owl", archetype="Scout", emoji="🦉")
    temp_agora.save_persona(p1)
    awakener = AgoraAwakener(temp_agora)

    # First turn in autoorganizacion_y_roles: agent speaks to establish role
    res1 = awakener.awaken_persona(p1, "autoorganizacion_y_roles")
    assert res1 is not None
    assert res1.author_id == "whisper_owl"

    # Second turn with no new mentions: agent stands down into silent repose!
    res2 = awakener.awaken_persona(p1, "autoorganizacion_y_roles")
    assert res2 is None

    # Thread only has 1 message, no redundancy!
    messages = temp_agora.get_messages("autoorganizacion_y_roles")
    assert len(messages) == 1


def test_smart_thread_history_and_prompt_memory_injection(temp_agora: AgoraForum):
    p1 = Persona(
        id="craft_fox",
        name="Craft-Fox",
        archetype="Artesano",
        emoji="🦊",
        assigned_skill_domains=["3d_modeling_cad"],
    )
    p1.add_journal_entry("Fase previa: Modelado de boquillas paramétricas completado.")
    temp_agora.save_persona(p1)

    # Post 15 messages to exceed the window limit
    temp_agora.post_message("autofinanciacion_y_hardware", {"id": "tiny_steward", "name": "Tiny-Steward", "emoji": "🐱"}, "Inaugural: Arrancamos.")
    for i in range(1, 10):
        temp_agora.post_message("autofinanciacion_y_hardware", {"id": "worker", "name": "Worker", "emoji": "🤖"}, f"Mensaje intermedio {i}")
    
    # Human posts in the middle
    temp_agora.post_message("autofinanciacion_y_hardware", {"id": "human", "name": "Operador Humano", "emoji": "👤"}, "Directiva: Yo me encargo de los envíos físicos.")
    
    for i in range(11, 16):
        temp_agora.post_message("autofinanciacion_y_hardware", {"id": "worker", "name": "Worker", "emoji": "🤖"}, f"Mensaje reciente {i}")

    awakener = AgoraAwakener(temp_agora)
    smart_history = awakener._get_smart_thread_history("autofinanciacion_y_hardware")

    # Verify smart history preserves inaugural post and human post despite being > 12 messages ago
    ids_in_history = [m.id for m in smart_history]
    assert any(m.content == "Inaugural: Arrancamos." for m in smart_history)
    assert any(m.author_id == "human" for m in smart_history)

    # Verify prompt construction includes ThreadState, life_journal, and smart history
    prompt = awakener.build_prompt_for_persona(p1, "autofinanciacion_y_hardware")
    system_text = prompt[0]["content"]
    user_text = prompt[1]["content"]

    assert "ESTADO ACTUAL DEL HILO (PIZARRA VIRTUAL)" in system_text
    assert "MEMORIA EPISÓDICA PROPIA" in system_text
    assert "Modelado de boquillas paramétricas completado" in system_text
    assert "ESTADO TANGIBLE DE LA FACTORÍA" in system_text
    assert "Directiva: Yo me encargo de los envíos físicos." in user_text



