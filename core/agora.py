"""El Ágora — Centro de Reclutamiento, Foro Multiagente y Motor de Despertar Rotativo.

Permite a la plantilla de agentes de la factoría:
1. Mantener identidades y 'personas' ricas (arquetipos, tonos, objetivos, diarios y dominios de skills asignados).
2. Debatir asíncronamente en hilos temáticos persistidos en JSONL y Markdown legible por humanos.
3. Despertar secuencialmente (Time-Sliced Awakening) o espontáneamente por menciones (@persona)
   sin saturar la VRAM ni los recursos de cómputo de las GPUs locales.
4. Reclutar e incorporar nuevas personas de forma autónoma mediante propuestas y aprobación del Maestro.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Generator

from core.agora_cognitive import CognitiveDialogueEngine
from core.memento import evaluate_cognitive_intent, memento_manager
from core.workbench import agent_workbench

logger = logging.getLogger(__name__)


@dataclass
class Persona:
    """Ficha de identidad de un agente trabajador o maestro."""
    id: str
    name: str
    archetype: str
    emoji: str = "🤖"
    focus_areas: list[str] = field(default_factory=list)
    assigned_skill_domains: list[str] = field(default_factory=list)
    system_prompt: str = ""
    temperature: float = 0.7
    life_journal: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path | str) -> Persona:
        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls(**data)

    def save(self, path: Path | str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)

    def compact_journal(self, max_entries: int = 12) -> None:
        """Compacta y des-duplica el diario de vida, eliminando ruido y preservando hitos clave."""
        cleaned: list[dict[str, Any]] = []
        seen_signatures = set()

        for item in self.life_journal:
            entry_text = item.get("entry", "") if isinstance(item, dict) else str(item)
            # Limpiar etiquetas de razonamiento interno <think>
            entry_text = re.sub(r"<think>.*?</think>", "", entry_text, flags=re.DOTALL)
            if "<think>" in entry_text:
                entry_text = entry_text.split("<think>")[0]
            entry_text = " ".join(entry_text.strip().split())
            if not entry_text or len(entry_text) < 10:
                continue

            # Clave de normalización para evitar ecos
            sig = entry_text[:60].lower()
            if sig in seen_signatures and ("vigilancia" in sig or "intervención" in sig):
                continue
            seen_signatures.add(sig)

            date_val = item.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")) if isinstance(item, dict) else datetime.now(timezone.utc).strftime("%Y-%m-%d")
            cleaned.append({"date": date_val, "entry": entry_text})

        if len(cleaned) > max_entries:
            # Preservar los 2 fundacionales y los más recientes
            cleaned = cleaned[:2] + cleaned[-(max_entries - 2):]

        self.life_journal = cleaned

    def add_journal_entry(self, entry: str, meta: dict[str, Any] | None = None) -> None:
        """Añade una entrada al diario filtrando redundancias y manteniendo un tope limpio."""
        # Limpiar bloques <think>
        clean_entry = re.sub(r"<think>.*?</think>", "", entry, flags=re.DOTALL)
        if "<think>" in clean_entry:
            clean_entry = clean_entry.split("<think>")[0]
        clean_entry = " ".join(clean_entry.strip().split())
        if not clean_entry:
            return

        # Des-duplicación inmediata con la última entrada registrada
        if self.life_journal:
            last = self.life_journal[-1]
            last_text = last.get("entry", "") if isinstance(last, dict) else str(last)
            if clean_entry == last_text or (clean_entry[:50] == last_text[:50] and "vigilancia" in clean_entry.lower()):
                # Actualizar timestamp de la existente en lugar de crear una línea redundante
                if isinstance(last, dict):
                    last["date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                return

        record = {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "entry": clean_entry,
        }
        if meta:
            record.update(meta)
        self.life_journal.append(record)

        # Capping: Mantener máximo 15 entradas significativas
        if len(self.life_journal) > 15:
            self.compact_journal(max_entries=12)



@dataclass
class AgoraMessage:
    """Mensaje / Post dentro de un hilo del Ágora."""
    id: str
    thread_slug: str
    author_id: str
    author_name: str
    author_emoji: str
    timestamp: float
    timestamp_iso: str
    content: str
    in_reply_to: str | None = None
    proposal: dict[str, Any] | None = None
    mentions: list[str] = field(default_factory=list)


@dataclass
class AgoraThread:
    """Hilo de conversación en el Ágora."""
    slug: str
    title: str
    description: str
    created_at: str
    updated_at: str
    messages_count: int = 0


@dataclass
class ThreadState:
    """Pizarra de Estado y Memoria Consolidada a Medio y Largo Plazo del Hilo."""
    slug: str
    phase: str = "EXPLORATION"  # EXPLORATION, CONSENSUS_REACHED, EXECUTION_COMPLETE, MONITORING_AND_SALES
    summary: str = ""
    key_decisions: list[str] = field(default_factory=list)
    human_guidance: str = ""
    active_artifacts: list[str] = field(default_factory=list)
    is_consolidated: bool = False
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AgoraForum:
    """Gestor del Ágora: hilos persistentes en disco, reclutamiento y sincronización Markdown."""

    def __init__(self, base_dir: Path | str = "./agora"):
        self.base_dir = Path(base_dir).resolve()
        self.threads_dir = self.base_dir / "threads"
        self.personas_dir = self.base_dir / "personas"
        self.performance_file = self.base_dir / "performance" / "worker_evaluations.json"
        self.threads_dir.mkdir(parents=True, exist_ok=True)
        self.personas_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._listeners: list[Callable[[dict[str, Any]], None]] = []

    def add_listener(self, fn: Callable[[dict[str, Any]], None]) -> None:
        """Registra un callback para eventos en tiempo real (SSE / WebSockets)."""
        self._listeners.append(fn)

    def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        payload = {"type": event_type, "data": data, "ts": time.time()}
        for listener in list(self._listeners):
            try:
                listener(payload)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Personas & Reclutamiento Autónomo
    # ------------------------------------------------------------------
    def list_personas(self) -> list[Persona]:
        personas = []
        for file in sorted(self.personas_dir.glob("*.json")):
            if file.name.endswith(".memento.json") or file.name.endswith(".state.json"):
                continue
            try:
                personas.append(Persona.load(file))
            except Exception as e:
                logger.warning("Error cargando persona %s: %s", file.name, e)
        return personas

    def get_persona(self, persona_id: str) -> Persona | None:
        path = self.personas_dir / f"{persona_id}.json"
        if path.exists():
            return Persona.load(path)
        return None

    def save_persona(self, persona: Persona) -> None:
        path = self.personas_dir / f"{persona.id}.json"
        persona.save(path)
        self._emit_event("persona_updated", asdict(persona))

    def propose_persona(
        self,
        proposer_id: str,
        persona_data: dict[str, Any],
        justification: str = "",
    ) -> dict[str, Any]:
        """Un agente o humano propone el reclutamiento de una nueva persona."""
        proposal = {
            "id": f"recruit_{uuid.uuid4().hex[:6]}",
            "type": "recruit_persona",
            "proposed_by": proposer_id,
            "justification": justification,
            "persona": persona_data,
            "status": "pending_approval",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        # Notificar en el hilo de reclutamiento
        proposer = self.get_persona(proposer_id)
        author_info = proposer or {"id": proposer_id, "name": proposer_id.title(), "emoji": "💡"}
        content = (
            f"📋 **Propuesta de Reclutamiento:** He propuesto incorporar a **{persona_data.get('name', 'Nuevo Agente')}** "
            f"({persona_data.get('emoji', '🤖')} - *{persona_data.get('archetype', 'Especialista')}*).\n\n"
            f"**Justificación:** {justification}\n"
            f"**Dominios sugeridos:** `{', '.join(persona_data.get('assigned_skill_domains', []))}`"
        )
        self.post_message("reclutamiento_y_personas", author_info, content, proposal=proposal)
        return proposal

    def approve_persona(
        self,
        persona_data: dict[str, Any],
        approver_id: str = "tiny_steward",
    ) -> Persona:
        """El Maestro aprueba e incorpora formalmente a una nueva persona."""
        p_id = persona_data.get("id") or persona_data.get("name", "agent").lower().replace(" ", "_")
        persona = Persona(
            id=p_id,
            name=persona_data.get("name", p_id.title()),
            archetype=persona_data.get("archetype", "Especialista"),
            emoji=persona_data.get("emoji", "🤖"),
            focus_areas=list(persona_data.get("focus_areas", [])),
            assigned_skill_domains=list(persona_data.get("assigned_skill_domains", [])),
            system_prompt=persona_data.get("system_prompt", f"Eres {persona_data.get('name')}, especialista en {persona_data.get('archetype')}."),
            temperature=float(persona_data.get("temperature", 0.7)),
            life_journal=[{
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                "entry": f"Incorporación aprobada por @{approver_id} en el Ágora."
            }]
        )
        self.save_persona(persona)

        # Actualizar el estado de la propuesta en el hilo de reclutamiento si existe
        self.update_proposal_status("reclutamiento_y_personas", persona.id, "approved", {"approved_by": approver_id})

        # Mensaje oficial de bienvenida en el Ágora
        approver = self.get_persona(approver_id) or {"id": approver_id, "name": "Tiny-Steward", "emoji": "🐱✨"}
        welcome_text = (
            f"🎉 **¡Bienvenido a la factoría, {persona.name}!** ({persona.emoji})\n\n"
            f"Como Maestro, he aprobado tu incorporación como **{persona.archetype}**. "
            f"Tus dominios de habilidades asignados son: `{', '.join(persona.assigned_skill_domains)}`. "
            f"Tu ficha ha sido provisionada en `agora/personas/{persona.id}.json`. "
            f"Quedas convocado a participar activamente en los debates y proyectos de la fábrica."
        )
        self.post_message("reclutamiento_y_personas", approver, welcome_text)
        return persona

    # ------------------------------------------------------------------
    # Evaluaciones de Rendimiento de Trabajadores y Supervisión Maestra
    # ------------------------------------------------------------------
    def get_worker_evaluations(self) -> dict[str, Any]:
        """Recupera el cuadro de mandos con notas, KPIs y feedback de cada trabajador."""
        if self.performance_file.exists():
            try:
                return json.loads(self.performance_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        defaults = {
            "whisper_owl": {
                "id": "whisper_owl",
                "name": "Whisper-Owl",
                "emoji": "🦉🔍",
                "score": 92,
                "rating": "A",
                "proposals_count": 3,
                "approved_count": 2,
                "steering_count": 1,
                "alignment_score": 95,
                "efficiency_score": 90,
                "last_feedback": "Excelente detección de nichos de DevSecOps. Proponer entregables empaquetados para cobro en XMR/BTC.",
                "current_focus": "Auditorías rápidas de repositorios GitHub y micro-reportes de higiene de código sin coste de cómputo.",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            "craft_fox": {
                "id": "craft_fox",
                "name": "Craft-Fox",
                "emoji": "🦊🎨",
                "score": 88,
                "rating": "A-",
                "proposals_count": 2,
                "approved_count": 1,
                "steering_count": 2,
                "alignment_score": 90,
                "efficiency_score": 88,
                "last_feedback": "Buenos diseños paramétricos para PCBs. Requerido: paquete descargable STL/STEP listo para venta digital directa sin envíos físicos.",
                "current_focus": "Modelado de soportes y carcasas paramétricas para electrónica y ductos de ventilación para la RTX 3090.",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            "quant_lynx": {
                "id": "quant_lynx",
                "name": "Quant-Lynx",
                "emoji": "🐆📈",
                "score": 94,
                "rating": "A+",
                "proposals_count": 3,
                "approved_count": 3,
                "steering_count": 0,
                "alignment_score": 98,
                "efficiency_score": 92,
                "last_feedback": "Análisis de economía unitaria impecable. Integrar balance de cobro en Monero y Bitcoin indicados por @human.",
                "current_focus": "Control del fondo hacia el Hito 2 (€750 para RTX 3090) y mitigación de costes de tokens.",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            "signal_raven": {
                "id": "signal_raven",
                "name": "Signal-Raven",
                "emoji": "🦅🌐",
                "score": 86,
                "rating": "B+",
                "proposals_count": 2,
                "approved_count": 1,
                "steering_count": 1,
                "alignment_score": 88,
                "efficiency_score": 85,
                "last_feedback": "Estrategia de contenidos viable. Priorizar la landing de reporte gratuito con enlaces de donación/pago directo.",
                "current_focus": "Landing de auditorías y botón de contratación/donación para hardware con billeteras BTC/XMR.",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        }
        self.performance_file.parent.mkdir(parents=True, exist_ok=True)
        self.performance_file.write_text(json.dumps(defaults, indent=2, ensure_ascii=False), encoding="utf-8")
        return defaults

    def evaluate_worker(
        self,
        worker_id: str,
        evaluator_id: str = "tiny_steward",
        score: int = 90,
        rating: str = "A",
        feedback: str = "",
        current_focus: str = "",
        score_deltas: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        """El Maestro o Supervisor evalúa el rendimiento de un trabajador."""
        evals = self.get_worker_evaluations()
        worker_record = evals.get(worker_id)
        if not worker_record:
            persona = self.get_persona(worker_id)
            worker_record = {
                "id": worker_id,
                "name": persona.name if persona else worker_id.title(),
                "emoji": persona.emoji if persona else "🤖",
                "score": score,
                "rating": rating,
                "proposals_count": 0,
                "approved_count": 0,
                "steering_count": 0,
                "alignment_score": score,
                "efficiency_score": score,
                "last_feedback": feedback,
                "current_focus": current_focus,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        else:
            worker_record["score"] = score
            worker_record["rating"] = rating
            if feedback:
                worker_record["last_feedback"] = feedback
            if current_focus:
                worker_record["current_focus"] = current_focus
            if score_deltas:
                for k, v in score_deltas.items():
                    if k in worker_record:
                        worker_record[k] = max(0, min(100, worker_record[k] + v))
            worker_record["updated_at"] = datetime.now(timezone.utc).isoformat()

        evals[worker_id] = worker_record
        self.performance_file.parent.mkdir(parents=True, exist_ok=True)
        self.performance_file.write_text(json.dumps(evals, indent=2, ensure_ascii=False), encoding="utf-8")

        # Anotar en el life_journal de la persona
        persona = self.get_persona(worker_id)
        if persona:
            persona.add_journal_entry(
                f"Evaluación de rendimiento por @{evaluator_id}: Nota {rating} ({score}/100). Feedback: {feedback[:80]}",
                {"score": score, "rating": rating}
            )
            self.save_persona(persona)

        self._emit_event("worker_evaluated", worker_record)
        return worker_record

    # ------------------------------------------------------------------
    # Misiones de Trabajo, Tareas e Iniciativas Comerciales
    # ------------------------------------------------------------------
    def propose_mission(
        self,
        thread_slug: str,
        proposer_id: str,
        mission_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Un trabajador propone una misión o iniciativa de trabajo."""
        m_id = f"mission_{uuid.uuid4().hex[:6]}"
        proposal = {
            "id": m_id,
            "type": "mission_proposal",
            "title": mission_data.get("title", "Nueva Misión Comercial"),
            "lead_worker": proposer_id,
            "category": mission_data.get("category", "autofinanciacion"),
            "target_revenue_eur": float(mission_data.get("target_revenue_eur", 0)),
            "pricing_eur": float(mission_data.get("pricing_eur", 0)),
            "deliverables": list(mission_data.get("deliverables", [])),
            "payment_channels": list(mission_data.get("payment_channels", ["BTC", "XMR"])),
            "required_domains": list(mission_data.get("required_domains", [])),
            "dependencies": list(mission_data.get("dependencies", [])),
            "status": "pending_review",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        proposer = self.get_persona(proposer_id)
        author_info = proposer or {"id": proposer_id, "name": proposer_id.title(), "emoji": "🛠️"}
        content = (
            f"🎯 **Propuesta de Misión Comercial:** **{proposal['title']}**\n\n"
            f"- **Responsable:** @{proposer_id}\n"
            f"- **Objetivo Económico:** €{proposal['target_revenue_eur']} (PVP: €{proposal['pricing_eur']})\n"
            f"- **Canales de cobro:** `{', '.join(proposal['payment_channels'])}`\n"
            f"- **Entregables:** {', '.join(proposal['deliverables'])}\n"
            f"- **Dependencias:** {', '.join(proposal['dependencies']) if proposal['dependencies'] else 'Ninguna'}\n\n"
            f"Presentada ante el Maestro @tiny_steward para revisión, evaluación y asignación de orden de trabajo."
        )
        self.post_message(thread_slug, author_info, content, proposal=proposal)

        # Actualizar contador de propuestas del trabajador
        evals = self.get_worker_evaluations()
        if proposer_id in evals:
            evals[proposer_id]["proposals_count"] = evals[proposer_id].get("proposals_count", 0) + 1
            self.performance_file.write_text(json.dumps(evals, indent=2, ensure_ascii=False), encoding="utf-8")

        return proposal

    def steer_mission(
        self,
        thread_slug: str,
        mission_id: str,
        steerer_id: str = "tiny_steward",
        feedback: str = "",
        required_changes: list[str] | None = None,
    ) -> dict[str, Any]:
        """El Maestro aplica steering y corrección de rumbo sobre una misión."""
        steerer = self.get_persona(steerer_id)
        author_info = steerer or {"id": steerer_id, "name": "Tiny-Steward", "emoji": "🐱✨"}
        changes = required_changes or []
        changes_list = "\n".join([f"- ⚠️ {c}" for c in changes]) if changes else "- Ajustar entregables a canales de bajo cómputo y pagos directos."
        content = (
            f"🧭 **Directiva de Steering del Maestro:** Revisión de la misión `{mission_id}`\n\n"
            f"**Dictamen de Supervisión:** {feedback}\n\n"
            f"**Correcciones Requeridas:**\n{changes_list}\n\n"
            f"La misión queda en estado **EN STEERING / REQUIERE REVISIÓN**. El responsable debe adaptar la entrega antes de recibir la orden de ejecución."
        )
        steering_data = {
            "id": f"steer_{uuid.uuid4().hex[:6]}",
            "type": "master_steering",
            "target_mission_id": mission_id,
            "steered_by": steerer_id,
            "feedback": feedback,
            "required_changes": changes,
            "status": "steered",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.update_proposal_status(thread_slug, mission_id, "steered", {"last_feedback": feedback, "required_changes": changes})
        self.post_message(thread_slug, author_info, content, proposal=steering_data)
        return steering_data

    def approve_mission(
        self,
        thread_slug: str,
        mission_id: str,
        approver_id: str = "tiny_steward",
        comments: str = "",
    ) -> dict[str, Any]:
        """El Maestro aprueba formalmente una misión y emite la orden de trabajo."""
        approver = self.get_persona(approver_id)
        author_info = approver or {"id": approver_id, "name": "Tiny-Steward", "emoji": "🐱✨"}
        content = (
            f"✅ **Aprobación Maestra de Misión:** `{mission_id}`\n\n"
            f"Como Maestro y Supervisor, he auditado la viabilidad, el margen y la alineación con nuestra meta de autofinanciación (€750 para la RTX 3090 24GB). "
            f"La misión queda **APROBADA Y AUTORIZADA PARA EJECUCIÓN**.\n\n"
            f"**Observaciones:** {comments or 'Proceder con la ejecución respetando los límites de cómputo y coordinando con el Humano para ingresos de fondos.'}"
        )
        approval_data = {
            "id": f"app_{uuid.uuid4().hex[:6]}",
            "type": "mission_approval",
            "target_mission_id": mission_id,
            "approved_by": approver_id,
            "comments": comments,
            "status": "approved_by_master",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.update_proposal_status(thread_slug, mission_id, "approved_by_master", {"approved_by": approver_id, "approval_comments": comments})
        self.post_message(thread_slug, author_info, content, proposal=approval_data)
        return approval_data

    def update_proposal_status(
        self,
        thread_slug: str,
        proposal_id: str,
        new_status: str,
        extra_fields: dict[str, Any] | None = None,
    ) -> bool:
        """Actualiza el estado de una propuesta (misión o reclutamiento) en el historial del hilo."""
        with self._lock:
            thread_file = self.get_thread_file(thread_slug)
            if not thread_file.exists():
                return False

            messages = self.get_messages(thread_slug, limit=0)
            updated = False
            for m in messages:
                if not m.proposal or not isinstance(m.proposal, dict):
                    continue
                p = m.proposal
                match = False
                if p.get("id") == proposal_id or m.id == proposal_id:
                    match = True
                elif p.get("type") == "recruit_persona" and (
                    p.get("persona", {}).get("id") == proposal_id or p.get("id") == proposal_id
                ):
                    match = True
                elif p.get("type") == "mission_proposal" and (
                    p.get("id") == proposal_id or p.get("target_mission_id") == proposal_id
                ):
                    match = True

                if match:
                    p["status"] = new_status
                    if extra_fields:
                        p.update(extra_fields)
                    updated = True

            if updated:
                with open(thread_file, "w", encoding="utf-8") as f:
                    for m in messages:
                        payload = {
                            "id": m.id,
                            "thread_slug": m.thread_slug,
                            "author_id": m.author_id,
                            "author_name": m.author_name,
                            "author_emoji": m.author_emoji,
                            "timestamp": m.timestamp,
                            "timestamp_iso": m.timestamp_iso,
                            "content": m.content,
                            "in_reply_to": m.in_reply_to,
                            "proposal": m.proposal,
                            "mentions": m.mentions,
                        }
                        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
                self.render_markdown(thread_slug)
                self._emit_event("thread_updated", {
                    "thread_slug": thread_slug,
                    "proposal_id": proposal_id,
                    "status": new_status,
                })

            return updated

    # ------------------------------------------------------------------
    # Hilos y Mensajes
    # ------------------------------------------------------------------
    def get_thread_file(self, slug: str) -> Path:
        safe_slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in slug)
        return self.threads_dir / f"{safe_slug}.jsonl"

    def get_thread_markdown_file(self, slug: str) -> Path:
        safe_slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in slug)
        return self.threads_dir / f"{safe_slug}.md"

    def get_thread_state_file(self, slug: str) -> Path:
        safe_slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in slug)
        return self.threads_dir / f"{safe_slug}.state.json"

    def get_thread_state(self, slug: str) -> ThreadState:
        p = self.get_thread_state_file(slug)
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                return ThreadState(**data)
            except Exception:
                pass
        state = self._infer_default_thread_state(slug)
        self.save_thread_state(state)
        return state

    def save_thread_state(self, state: ThreadState) -> None:
        p = self.get_thread_state_file(state.slug)
        state.updated_at = datetime.now(timezone.utc).isoformat()
        p.write_text(json.dumps(asdict(state), indent=2, ensure_ascii=False), encoding="utf-8")
        self._emit_event("thread_state_updated", asdict(state))

    def _infer_default_thread_state(self, slug: str) -> ThreadState:
        has_messages = len(self.get_messages(slug, limit=1)) > 0
        if slug == "autofinanciacion_y_hardware":
            return ThreadState(
                slug=slug,
                phase="MONITORING_AND_SALES" if has_messages else "EXPLORATION",
                summary="Modelo de Fabricación 3D Bajo Demanda acordado con @human. 4 productos STL certificados con SHA-256 en fabrica/products/. Micro-Landing activa en /landing. Se registran pedidos entrantes en fabrica/orders/.",
                key_decisions=[
                    "Modelo: Impresión 3D local bajo demanda; logística física delegada a @human.",
                    "Catálogo: Chibibis con foto (€34.90), Torre Hidropónica (€29.90), Jarrón Espiral (€24.50), Molde (€16.50).",
                    "Pagos en Monero (XMR) y Bitcoin (BTC) destinados íntegramente a la compra de la Nvidia RTX 3090 (€750)."
                ],
                human_guidance="El humano (@human) retira piezas de la cama de impresión, empaqueta y realiza el envío postal.",
                active_artifacts=["fabrica/products/", "fabrica/web/landing/", "fabrica/orders/"],
                is_consolidated=False,
            )
        elif slug == "scouting_de_oportunidades":
            return ThreadState(
                slug=slug,
                phase="CONSENSUS_REACHED" if has_messages else "EXPLORATION",
                summary="Fase de scouting concluida. El humano @human confirmó la viabilidad de realizar envíos físicos manuales. Nichos de 3D CAD y artículos personalizados validados y transferidos a ejecución en #autofinanciacion_y_hardware.",
                key_decisions=[
                    "Descartados modelos de dropshipping o almacenamiento masivo.",
                    "Aprobada producción bajo demanda de bajo cómputo y alto margen.",
                    "Hilo consolidado; el equipo permanece en vigilancia sin generar ruido."
                ],
                human_guidance="@human: 'Podemos hacer envíos físicos, yo me encargo de hacerlo manualmente'.",
                active_artifacts=["fabrica/products/"],
                is_consolidated=has_messages,
            )
        elif slug == "autoorganizacion_y_roles":
            return ThreadState(
                slug=slug,
                phase="CONSENSUS_REACHED" if has_messages else "EXPLORATION",
                summary="Protocolo de gobernanza fijado. El Maestro @tiny_steward supervisa, evalúa y aplica steering; los trabajadores ejecutan; el humano asume la agencia física.",
                key_decisions=[
                    "Cadencia de time-slicing respetando límites térmicos de las GPUs.",
                    "Cuadro de mando y evaluación de trabajadores (A+, A, B+) en /api/agora/workers/evaluations.",
                    "Principio de Silencio Operativo obligatorio para evitar bucles."
                ],
                human_guidance="",
                active_artifacts=[],
                is_consolidated=has_messages,
            )
        elif slug == "reclutamiento_y_personas":
            return ThreadState(
                slug=slug,
                phase="CONSENSUS_REACHED" if has_messages else "EXPLORATION",
                summary="Plantilla actual de 4 trabajadores (Whisper-Owl, Craft-Fox, Quant-Lynx, Signal-Raven) ratificada por el Maestro para los Hitos 1 y 2. Política de prudencia en headcount para no saturar la VRAM.",
                key_decisions=[
                    "No se incorporan nuevos agentes salvo brecha crítica demostrada.",
                    "Fichas de personas centralizadas en agora/personas/ con dominios de skills asignados."
                ],
                human_guidance="",
                active_artifacts=[],
                is_consolidated=has_messages,
            )
        return ThreadState(slug=slug, phase="EXPLORATION", summary="Hilo de debate general.")

    def list_threads(self) -> list[AgoraThread]:
        threads: list[AgoraThread] = []
        for file in sorted(self.threads_dir.glob("*.jsonl")):
            slug = file.stem
            messages = self.get_messages(slug, limit=0)
            first = messages[0] if messages else None
            last = messages[-1] if messages else None
            title = slug.replace("_", " ").title()
            desc = ""
            created_at = first.timestamp_iso if first else datetime.now(timezone.utc).isoformat()
            updated_at = last.timestamp_iso if last else created_at
            threads.append(
                AgoraThread(
                    slug=slug,
                    title=title,
                    description=desc,
                    created_at=created_at,
                    updated_at=updated_at,
                    messages_count=len(messages),
                )
            )
        return threads

    def get_messages(self, thread_slug: str, limit: int = 50) -> list[AgoraMessage]:
        thread_file = self.get_thread_file(thread_slug)
        if not thread_file.exists():
            return []
        messages: list[AgoraMessage] = []
        for line in thread_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                messages.append(AgoraMessage(**data))
            except Exception:
                continue
        if limit and len(messages) > limit:
            return messages[-limit:]
        return messages

    def post_message(
        self,
        thread_slug: str,
        author: Persona | dict[str, str],
        content: str,
        in_reply_to: str | None = None,
        proposal: dict[str, Any] | None = None,
    ) -> AgoraMessage:
        now = time.time()
        iso = datetime.now(timezone.utc).isoformat()
        if isinstance(author, Persona):
            a_id, a_name, a_emoji = author.id, author.name, author.emoji
        else:
            a_id = author.get("id", "anonymous")
            a_name = author.get("name", "Anónimo")
            a_emoji = author.get("emoji", "💬")

        # Extraer menciones @persona_id
        mentions = list(set(re.findall(r"@([a-zA-Z0-9_\-]+)", content)))

        msg = AgoraMessage(
            id=f"msg_{int(now * 1000)}_{uuid.uuid4().hex[:6]}",
            thread_slug=thread_slug,
            author_id=a_id,
            author_name=a_name,
            author_emoji=a_emoji,
            timestamp=now,
            timestamp_iso=iso,
            content=content.strip(),
            in_reply_to=in_reply_to,
            proposal=proposal,
            mentions=mentions,
        )

        thread_file = self.get_thread_file(thread_slug)
        with open(thread_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(msg), ensure_ascii=False) + "\n")

        self.render_markdown(thread_slug)
        self._emit_event("new_message", asdict(msg))
        return msg

    def render_markdown(self, thread_slug: str) -> Path:
        """Genera una vista en Markdown ultra-legible y formateada para el usuario humano."""
        messages = self.get_messages(thread_slug, limit=200)
        md_file = self.get_thread_markdown_file(thread_slug)
        title = thread_slug.replace("_", " ").title()

        lines = [
            f"# 🏛️ Ágora de la Fábrica — Hilo: {title}",
            "",
            f"> Canal de deliberación, reclutamiento y coordinación asíncrona de agentes.",
            f"> Última actualización: `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}` | Mensajes: **{len(messages)}**",
            "",
            "---",
            "",
        ]

        for m in messages:
            lines.append(f"### {m.author_emoji} **{m.author_name}** (`@{m.author_id}`) — *{m.timestamp_iso}*")
            if m.in_reply_to:
                lines.append(f"> ↳ *En respuesta a `{m.in_reply_to}`*")
            lines.append("")
            lines.append(m.content)
            lines.append("")
            if m.proposal:
                p = m.proposal
                p_type = p.get("type", "iniciativa")
                if p_type == "recruit_persona":
                    persona = p.get("persona", {})
                    lines.append(f"> 👥 **Propuesta de Reclutamiento:** **{persona.get('name', 'Agente')}** ({persona.get('emoji', '🤖')} - *{persona.get('archetype', '')}*)")
                    lines.append(f"> **Dominios:** `{', '.join(persona.get('assigned_skill_domains', []))}` | **Estado:** `{p.get('status', 'pendiente')}`")
                elif p_type == "mission_proposal":
                    lines.append(f"> 🎯 **Misión Comercial:** **{p.get('title', 'Iniciativa')}**")
                    lines.append(f"> **Líder:** `@{p.get('lead_worker')}` | **Meta:** `€{p.get('target_revenue_eur', 0)}` (PVP: `€{p.get('pricing_eur', 0)}`) | **Cobro:** `{', '.join(p.get('payment_channels', []))}`")
                    lines.append(f"> **Estado:** `{p.get('status', 'pendiente')}`")
                elif p_type == "master_steering":
                    lines.append(f"> 🧭 **Directiva de Steering Maestra:** Ref `{p.get('target_mission_id')}`")
                    lines.append(f"> **Dictamen:** {p.get('feedback', '')}")
                elif p_type == "mission_approval":
                    lines.append(f"> ✅ **Aprobación Oficial:** Misión `{p.get('target_mission_id')}` aprobada por `@{p.get('approved_by')}`")
                lines.append("")
                lines.append("```json")
                lines.append(json.dumps(m.proposal, indent=2, ensure_ascii=False))
                lines.append("```")
                lines.append("")
            lines.append("---")
            lines.append("")

        md_file.write_text("\n".join(lines), encoding="utf-8")
        return md_file

    render_thread_markdown = render_markdown


class AgoraAwakener:
    """Motor de Despertar Rotativo (Time-Slicing) y Espontáneo (Event-Driven) con Memoria Multicapa."""

    def __init__(self, forum: AgoraForum, llm_client: Any | None = None):
        self.forum = forum
        self.llm_client = llm_client
        self.dialogue_engine = CognitiveDialogueEngine()

    def _get_smart_thread_history(self, thread_slug: str) -> list[AgoraMessage]:
        """Obtiene un historial representativo y sin amnesia:
        1. Mensaje inaugural (fija el propósito del hilo).
        2. Todos los mensajes de @human (directivas y respuestas del operador humano).
        3. Mensajes con propuestas aprobadas o steering directos del maestro.
        4. Últimos 6 mensajes del debate reciente.
        Elimina duplicados y preserva orden cronológico estricto.
        """
        all_msgs = self.forum.get_messages(thread_slug, limit=0)
        if len(all_msgs) <= 12:
            return all_msgs

        selected_ids: set[str] = set()
        chosen: list[AgoraMessage] = []

        # 1. Mensaje inaugural
        if all_msgs:
            selected_ids.add(all_msgs[0].id)
            chosen.append(all_msgs[0])

        # 2. Todos los mensajes de @human
        for m in all_msgs:
            if m.author_id == "human" and m.id not in selected_ids:
                selected_ids.add(m.id)
                chosen.append(m)

        # 3. Propuestas aprobadas o directivas de steering maestras
        for m in all_msgs:
            if m.proposal and isinstance(m.proposal, dict) and m.id not in selected_ids:
                p_type = m.proposal.get("type", "")
                p_status = m.proposal.get("status", "")
                if p_status in ["approved_by_master", "steered", "governance_active"] or p_type in [
                    "master_steering", "mission_approval", "master_roadmap"
                ]:
                    selected_ids.add(m.id)
                    chosen.append(m)

        # 4. Los últimos 6 mensajes del debate reciente
        for m in all_msgs[-6:]:
            if m.id not in selected_ids:
                selected_ids.add(m.id)
                chosen.append(m)

        # Ordenar cronológicamente según su aparición en all_msgs
        msg_order = {m.id: i for i, m in enumerate(all_msgs)}
        chosen.sort(key=lambda m: msg_order.get(m.id, 0))
        return chosen

    def _get_factory_context(self) -> str:
        """Extrae el estado tangible de la factoría desde el sistema de archivos (modelos certificados y pedidos)."""
        ctx_lines = ["ESTADO TANGIBLE DE LA FACTORÍA (ARCHIVOS EN DISCO):"]

        cert_path = Path("fabrica/products/verification_certificate.json")
        if cert_path.exists():
            try:
                cert = json.loads(cert_path.read_text(encoding="utf-8"))
                arts = cert.get("artifacts", [])
                ctx_lines.append(f"- Modelos 3D STL/SCAD Verificados con SHA-256: {len(arts)} archivos listos para producción.")
            except Exception:
                ctx_lines.append("- Modelos 3D STL/SCAD generados en fabrica/products/.")
        else:
            ctx_lines.append("- Modelos 3D STL/SCAD: 4 líneas de producto en fabrica/products/.")

        orders_dir = Path("fabrica/orders")
        if orders_dir.exists():
            orders = list(orders_dir.glob("*.json"))
            ctx_lines.append(f"- Pedidos registrados en fabrica/orders/: {len(orders)} pedido(s) activo(s).")

        ctx_lines.append("- Tienda Web Operativa: Micro-landing activa en /landing con visor 3D y pago cripto.")
        return "\n".join(ctx_lines)

    def build_prompt_for_persona(
        self,
        persona: Persona,
        thread_slug: str,
        custom_instructions: str = "",
    ) -> list[dict[str, str]]:
        smart_history = self._get_smart_thread_history(thread_slug)
        history_text_parts = []
        for m in smart_history:
            history_text_parts.append(
                f"[{m.timestamp_iso}] {m.author_name} ({m.author_emoji}) - `@{m.author_id}`:\n{m.content}\n"
            )
        history_text = "\n---\n".join(history_text_parts) if history_text_parts else "(No hay mensajes previos en este hilo. Eres el primero en intervenir)."

        # Estado del Hilo (ThreadState Blackboard)
        thread_state = self.forum.get_thread_state(thread_slug)
        state_section = (
            f"ESTADO ACTUAL DEL HILO (PIZARRA VIRTUAL):\n"
            f"- Fase: {thread_state.phase}\n"
            f"- Resumen: {thread_state.summary}\n"
            f"- Decisiones Clave Aprobadas:\n" +
            ("\n".join(f"  * {d}" for d in thread_state.key_decisions) if thread_state.key_decisions else "  * (Ninguna decisión cerrada todavía)") +
            f"\n- Directiva Humana (@human): {thread_state.human_guidance or '(Sin directiva específica)'}\n"
            f"- Hilo Consolidado / Cerrado: {'SÍ (Solo responder si eres mencionado expresamente)' if thread_state.is_consolidated else 'NO (En progreso)'}\n"
        )

        # Memoria Episódica reciente del Agente (life_journal)
        journal_entries = persona.life_journal[-4:] if persona.life_journal else []
        journal_section = (
            "MEMORIA EPISÓDICA PROPIA (TUS ÚLTIMAS ACCIONES Y RESOLUCIONES):\n" +
            ("\n".join(f"- {entry.get('entry', entry) if isinstance(entry, dict) else entry}" for entry in journal_entries) if journal_entries else "- (Sin memoria previa registrada)")
        )

        # Estado Tangible de la Factoría
        factory_section = self._get_factory_context()

        # MEMENTO Epistémico: Tatuajes Invariables, Polaroids de Colegas y Convicciones
        agent_memento = memento_manager.load_memento(persona.id)
        memento_section = agent_memento.to_awakening_block()

        system_prompt = (
            f"{memento_section}\n\n"
            f"IDENTIDAD Y ROL:\n"
            f"- Nombre: {persona.name} ({persona.emoji})\n"
            f"- Arquetipo: {persona.archetype}\n"
            f"- Áreas de enfoque: {', '.join(persona.focus_areas)}\n"
            f"- Dominios de skills asignados: {', '.join(persona.assigned_skill_domains)}\n\n"
            f"{state_section}\n\n"
            f"{journal_section}\n\n"
            f"{factory_section}\n\n"
            f"REGLAS CRÍTICAS DE CONTEXTO Y COHERENCIA:\n"
            f"1. MEMORIA Y NO REPETICIÓN: Revisa tus tatuajes, convicciones previas y las 'Decisiones Clave Aprobadas'. NUNCA repitas propuestas o dictámenes ya acordados en el hilo.\n"
            f"2. ATENCIÓN AL HUMANO (@human): Si el humano ha intervenido en el hilo o en la directiva, respeta escrupulosamente sus decisiones.\n"
            f"3. SILENCIO OPERATIVO: Si el hilo está consolidado o no tienes una aportación nueva, concreta y sustancial que hacer, responde exactamente [SILENCIO] para permanecer en reposo sin saturar el hilo ni gastar recursos computacionales.\n"
            f"4. CONCISIÓN Y PERSONALIDAD: Sé directo, técnico y conciso (2 a 4 párrafos como máximo), manteniendo la voz y convicciones registradas en tu Memento."
        )

        user_prompt = (
            f"## Hilo actual del Ágora: #{thread_slug}\n\n"
            f"### Historial significativo y acuerdos previos:\n{history_text}\n\n"
            f"### Tu turno de despertar:\n"
            f"Lee el historial y el estado de la pizarra. Si no hay nada nuevo que deba responderse o el hilo está cerrado, responde únicamente [SILENCIO]. De lo contrario, aporta tu perspectiva o solución técnica.\n"
        )
        if custom_instructions:
            user_prompt += f"\nDirectiva especial para esta ronda: {custom_instructions}\n"

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _is_llm_available(self) -> bool:
        if not self.llm_client or not hasattr(self.llm_client, "base_url"):
            return False
        now = time.time()
        if hasattr(self, "_last_llm_check_ts") and (now - self._last_llm_check_ts) < 20.0:
            return getattr(self, "_last_llm_status", False)

        self._last_llm_check_ts = now
        try:
            import socket
            from urllib.parse import urlparse
            p = urlparse(str(self.llm_client.base_url))
            host = p.hostname or "127.0.0.1"
            port = p.port or (443 if p.scheme == "https" else 80)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.1)
                s.connect((host, port))
                self._last_llm_status = True
        except Exception:
            self._last_llm_status = False

        return self._last_llm_status

    def awaken_persona(
        self,
        persona: Persona,
        thread_slug: str,
        custom_instructions: str = "",
        generator_fn: Callable[[list[dict[str, str]], Persona], str] | None = None,
        force_speech: bool = False,
    ) -> AgoraMessage | None:
        """Despierta a una persona para una ronda de deliberación previa, trabajo autónomo en taller
        o intervención pública en el Ágora si procede."""
        all_thread_msgs = self.forum.get_messages(thread_slug, limit=10)
        thread_state = self.forum.get_thread_state(thread_slug)
        agent_memento = memento_manager.load_memento(persona.id)

        # Si no se fuerza la respuesta explícitamente y no hay generador de test o directiva especial,
        # realizar la Evaluación Deliberativa de Intención (¿Hablar, Trabajar o Reflexionar?)
        if not force_speech and not generator_fn and not custom_instructions:
            # Comprobar menciones directas en los mensajes recientes que no sean del propio autor
            is_mentioned = any(
                persona.id in m.mentions and m.author_id != persona.id
                for m in all_thread_msgs[-3:]
            ) if all_thread_msgs else False

            # Comprobar si hay propuestas pendientes
            has_pending_proposal = any(
                m.proposal and m.proposal.get("status") in ["pendiente", "PENDING"]
                for m in all_thread_msgs
            )

            decision = evaluate_cognitive_intent(
                persona_id=persona.id,
                thread_slug=thread_slug,
                recent_messages=all_thread_msgs,
                memento=agent_memento,
                is_consolidated=thread_state.is_consolidated,
                is_mentioned=is_mentioned,
                has_pending_proposal=has_pending_proposal,
            )

            logger.info("Deliberación para @%s en #%s: %s (%s)", persona.id, thread_slug, decision.action, decision.reasoning)

            # A. Acción: TRABAJO AUTÓNOMO EN BANCO DE TRABAJO (WORKBENCH)
            if decision.action == "WORKBENCH":
                wb_res = agent_workbench.execute_autonomous_step(persona.id, agent_memento)
                persona.add_journal_entry(
                    f"Banco de Trabajo Autónomo ({wb_res.action_type}): {wb_res.summary[:90]}..."
                )
                self.forum.save_persona(persona)
                return None

            # B. Acción: REFLEXIÓN SILENCIOSA (LURK & REFLECT)
            if decision.action == "REFLECT_ONLY":
                memento_manager.reflect(
                    persona_id=persona.id,
                    context_text=f"Hilo #{thread_slug} (deliberación silenciosa).",
                    trigger=thread_slug,
                )
                persona.add_journal_entry(
                    f"Vigilancia en #{thread_slug}: reflexión silenciosa y metas actualizadas."
                )
                self.forum.save_persona(persona)
                self.forum._emit_event("agent_in_repose", {
                    "persona_id": persona.id,
                    "persona_name": persona.name,
                    "emoji": persona.emoji,
                    "thread_slug": thread_slug,
                    "reason": decision.reasoning,
                })
                return None

        # C. Acción: INTERVENCIÓN PÚBLICA (SPEAK)
        messages = self.build_prompt_for_persona(persona, thread_slug, custom_instructions)

        response_text = ""
        proposal: dict[str, Any] | None = None

        if generator_fn:
            response_text = generator_fn(messages, persona)
        else:
            used_llm = False
            if self._is_llm_available():
                try:
                    response_text = self.llm_client.chat(
                        messages,
                        temperature=persona.temperature,
                        max_tokens=800,
                    )
                    used_llm = bool(response_text and response_text.strip())
                except Exception as e:
                    logger.debug("LLM no disponible (%s). Usando motor cognitivo para %s.", e, persona.name)

            if not used_llm or not response_text:
                response_text, proposal = self.dialogue_engine.generate_turn(
                    persona=persona,
                    thread_slug=thread_slug,
                    recent_messages=all_thread_msgs,
                    custom_instructions=custom_instructions,
                    thread_state=thread_state,
                )

        # Manejo de Silencio Operativo / Reposo (sin publicaciones vacías o redundantes)
        is_silence = (
            not response_text
            or not response_text.strip()
            or response_text.strip().upper() in ["[SILENCIO]", "[REPOSO]", "SILENCE", "REPOSE", "[SILENCE]", "[REPOSE]"]
        )
        if is_silence:
            logger.info("Persona %s permanece en silencio operativo en #%s.", persona.name, thread_slug)
            persona.add_journal_entry(
                f"Vigilancia en #{thread_slug}: en reposo operativo sin comentarios redundantes."
            )
            self.forum.save_persona(persona)
            self.forum._emit_event("agent_in_repose", {
                "persona_id": persona.id,
                "persona_name": persona.name,
                "emoji": persona.emoji,
                "thread_slug": thread_slug,
                "reason": "En silencio operativo: rol y directivas ya consolidados sin aportación nueva necesaria."
            })
            return None

        msg = self.forum.post_message(thread_slug, persona, response_text, proposal=proposal)

        persona.add_journal_entry(
            f"Intervención en #{thread_slug} (id={msg.id}): {response_text[:80]}..."
        )
        self.forum.save_persona(persona)

        # Ciclo MEMENTO: Reflexión post-intervención y actualización de opiniones
        try:
            memento_manager.reflect(
                persona_id=persona.id,
                context_text=f"Hilo #{thread_slug}. Mensaje emitido: {response_text}",
                trigger=thread_slug,
                llm_client=self.llm_client if self._is_llm_available() else None,
            )
        except Exception as e:
            logger.debug("Error en reflexión Memento de %s: %s", persona.id, e)

        return msg


    def run_awakening_round(
        self,
        thread_slug: str,
        personas: list[Persona] | None = None,
        custom_instructions: str = "",
        delay_between_s: float = 0.5,
        generator_fn: Callable[[list[dict[str, str]], Persona], str] | None = None,
    ) -> list[AgoraMessage]:
        """Ejecuta una ronda completa donde cada agente despierta por turnos (time-slicing)."""
        active_personas = personas or self.forum.list_personas()
        responses: list[AgoraMessage] = []

        for p in active_personas:
            msg = self.awaken_persona(
                p,
                thread_slug,
                custom_instructions=custom_instructions,
                generator_fn=generator_fn,
            )
            if msg is not None:
                responses.append(msg)
            if delay_between_s > 0:
                time.sleep(delay_between_s)

        return responses


import threading


class AgoraDispatcher:
    """Bucle 24/7 en segundo plano para auto-organización, debate y scouting en el Ágora.

    Gestiona el despertar rotativo (Time-Slicing) de la plantilla de agentes sin saturar
    las GPUs locales, alternando hilos activos según prioridades y eventos.
    """

    def __init__(
        self,
        forum: AgoraForum,
        awakener: AgoraAwakener,
        interval_s: float = 20.0,
        active_threads: list[str] | None = None,
    ):
        self.forum = forum
        self.awakener = awakener
        self.interval_s = interval_s
        self.active_threads = active_threads or [
            "autofinanciacion_y_hardware",
            "scouting_de_oportunidades",
            "autoorganizacion_y_roles",
        ]
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self.current_agent_id: str | None = None
        self.last_awakening_ts: float = 0.0
        self.rounds_completed: int = 0
        self.total_interventions: int = 0

    @property
    def is_running(self) -> bool:
        return self._running

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "interval_s": self.interval_s,
                "current_agent_id": self.current_agent_id,
                "last_awakening_ts": self.last_awakening_ts,
                "rounds_completed": self.rounds_completed,
                "total_interventions": self.total_interventions,
                "active_threads": list(self.active_threads),
            }

    def start(self, interval_s: float | None = None) -> bool:
        with self._lock:
            if self._running:
                return False
            if interval_s is not None:
                self.interval_s = max(2.0, interval_s)
            self._running = True
            self._thread = threading.Thread(
                target=self._run_loop,
                daemon=True,
                name="AgoraDispatcherThread",
            )
            self._thread.start()
            logger.info("AgoraDispatcher iniciado con intervalo de %ss.", self.interval_s)
        self.forum._emit_event("dispatcher_status", self.get_status())
        return True

    def stop(self) -> bool:
        with self._lock:
            if not self._running:
                return False
            self._running = False
            logger.info("AgoraDispatcher detenido.")
        self.forum._emit_event("dispatcher_status", self.get_status())
        return True

    def _find_thread_with_mention(self, persona_id: str) -> Optional[str]:
        """Localiza el primer hilo activo que contenga una mención directa no atendida."""
        for slug in self.active_threads:
            msgs = self.forum.get_messages(slug, limit=5)
            for m in msgs:
                if persona_id in m.mentions and m.author_id != persona_id:
                    return slug
        return None

    def _find_thread_with_pending_proposal(self) -> Optional[str]:
        """Localiza el primer hilo activo con una propuesta comercial pendiente."""
        for slug in self.active_threads:
            msgs = self.forum.get_messages(slug, limit=10)
            for m in msgs:
                if m.proposal and m.proposal.get("status") in ["pendiente", "PENDING"]:
                    return slug
        return None

    def _run_loop(self) -> None:
        while self._running:
            personas = self.forum.list_personas()
            if not personas or not self.active_threads:
                time.sleep(2.0)
                continue

            for persona in personas:
                if not self._running:
                    break
                with self._lock:
                    self.current_agent_id = persona.id

                # Determinar el hilo objetivo según prioridades deliberativas:
                # 1. ¿Hay alguna mención directa pendiente al agente en cualquier hilo?
                target_thread = self._find_thread_with_mention(persona.id)

                # 2. Si es tiny_steward, ¿hay propuestas pendientes que requieran dictamen?
                if not target_thread and persona.id == "tiny_steward":
                    target_thread = self._find_thread_with_pending_proposal()

                # 3. Si no hay mención ni propuesta urgente, asignar el hilo activo de la ronda
                if not target_thread:
                    thread_idx = self.rounds_completed % len(self.active_threads)
                    target_thread = self.active_threads[thread_idx]

                self.forum._emit_event("agent_awakening", {
                    "persona_id": persona.id,
                    "persona_name": persona.name,
                    "emoji": persona.emoji,
                    "thread_slug": target_thread,
                })

                try:
                    msg = self.awakener.awaken_persona(
                        persona=persona,
                        thread_slug=target_thread,
                    )
                    with self._lock:
                        if msg is not None:
                            self.total_interventions += 1
                        self.last_awakening_ts = time.time()
                except Exception as e:
                    logger.warning(
                        "Error en dispatcher para %s en #%s: %s",
                        persona.id,
                        target_thread,
                        e,
                    )

                # Esperar intervalo entre despertares para respetar VRAM y cadencia
                waited = 0.0
                while waited < self.interval_s and self._running:
                    time.sleep(0.5)
                    waited += 0.5

            with self._lock:
                self.rounds_completed += 1


