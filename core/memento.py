"""Módulo Central MEMENTO: Sistema Epistémico de Formación de Opiniones,

Tatuajes Invariables y Gestión Fuerte de Prompts de Sistema.

Inspirado en la obra 'Memento': los LLMs sufren amnesia anterógrada entre turnos.
Este módulo provee la pizarra epistémica persistente (Memento Slate) donde cada agente
graba sus axiomas inmutables (tatuajes), sus impresiones vivas sobre sus compañeros
(polaroids) y sus convicciones técnicas y comerciales evolucionadas.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("tiny_steward.memento")
_MEMENTO_LOCK = threading.RLock()


@dataclass
class PeerImpression:
    """Polaroid mental con nota manuscrita sobre un compañero."""
    persona_id: str
    relationship: str
    impression: str
    trust_level: float = 0.85
    last_updated_iso: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PeerImpression:
        return cls(
            persona_id=data.get("persona_id", ""),
            relationship=data.get("relationship", "Compañero"),
            impression=data.get("impression", ""),
            trust_level=float(data.get("trust_level", 0.85)),
            last_updated_iso=data.get("last_updated_iso", datetime.now(timezone.utc).isoformat()),
        )


@dataclass
class OpinionEntry:
    """Convicción o postura temática del agente."""
    topic: str
    stance: str
    confidence: float = 0.85
    evidence_summary: str = ""
    last_updated_iso: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OpinionEntry:
        return cls(
            topic=data.get("topic", ""),
            stance=data.get("stance", ""),
            confidence=float(data.get("confidence", 0.85)),
            evidence_summary=data.get("evidence_summary", ""),
            last_updated_iso=data.get("last_updated_iso", datetime.now(timezone.utc).isoformat()),
        )


@dataclass
class EpistemicShift:
    """Registro histórico de un cambio de opinión o salto cognitivo."""
    date_iso: str
    trigger: str
    previous_belief: str
    new_belief: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DeliberationDecision:
    """Decisión deliberativa previa: hablar en público, reflexionar en silencio o trabajar en privado."""
    persona_id: str
    action: str  # "SPEAK", "REFLECT_ONLY", "WORKBENCH"
    reasoning: str
    target_thread: Optional[str] = None
    task_focus: Optional[str] = None
    created_at_iso: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AgentMemento:
    """Pizarra Epistémica y Almacén de Tatuajes Invariables de un Agente."""
    persona_id: str
    version: str = "1.0.0"
    raison_d_etre: str = ""
    core_tattoos: List[str] = field(default_factory=list)
    opinions: Dict[str, OpinionEntry] = field(default_factory=dict)
    peer_dossier: Dict[str, PeerImpression] = field(default_factory=dict)
    open_hypotheses: List[str] = field(default_factory=list)
    personal_goals: List[str] = field(default_factory=list)
    workbench_task: Optional[Dict[str, Any]] = None
    workbench_history: List[Dict[str, Any]] = field(default_factory=list)
    evolution_log: List[EpistemicShift] = field(default_factory=list)
    last_reflection_iso: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def add_personal_goal(self, goal: str) -> None:
        """Añade un objetivo personal operativo o de desarrollo."""
        clean = goal.strip()
        if clean and clean not in self.personal_goals:
            self.personal_goals.append(clean)
            self.last_reflection_iso = datetime.now(timezone.utc).isoformat()

    def remove_personal_goal(self, index: int) -> bool:
        if 0 <= index < len(self.personal_goals):
            self.personal_goals.pop(index)
            self.last_reflection_iso = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def set_workbench_task(
        self,
        title: str,
        description: str,
        deliverable: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Asigna o inicia una tarea de banco de trabajo autónomo individual."""
        task = {
            "task_id": f"wb_{int(datetime.now(timezone.utc).timestamp())}_{self.persona_id}",
            "title": title,
            "description": description,
            "status": "IN_PROGRESS",
            "deliverable": deliverable,
            "started_at_iso": datetime.now(timezone.utc).isoformat(),
            "updated_at_iso": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
            "steps_log": [],
        }
        self.workbench_task = task
        self.last_reflection_iso = datetime.now(timezone.utc).isoformat()
        return task

    def log_workbench_step(self, step_note: str, artifacts: Optional[List[str]] = None) -> None:
        """Registra un avance o paso ejecutado de forma autónoma en el taller."""
        if not self.workbench_task:
            self.set_workbench_task("Trabajo Autónomo", "Avance individual en taller")
        self.workbench_task["updated_at_iso"] = datetime.now(timezone.utc).isoformat()
        self.workbench_task.setdefault("steps_log", []).append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "note": step_note,
            "artifacts": artifacts or [],
        })
        self.last_reflection_iso = datetime.now(timezone.utc).isoformat()

    def complete_workbench_task(self, result_summary: str, artifacts: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """Completa la tarea del banco de trabajo y la traslada al historial histórico."""
        if not self.workbench_task:
            return None
        self.workbench_task["status"] = "COMPLETED"
        self.workbench_task["completed_at_iso"] = datetime.now(timezone.utc).isoformat()
        self.workbench_task["result_summary"] = result_summary
        self.workbench_task["artifacts"] = artifacts or []
        completed = dict(self.workbench_task)
        self.workbench_history.append(completed)
        if len(self.workbench_history) > 25:
            self.workbench_history = self.workbench_history[-25:]
        self.workbench_task = None
        self.last_reflection_iso = datetime.now(timezone.utc).isoformat()
        return completed

    def add_tattoo(self, axiom: str) -> None:
        """Inscribe un tatuaje invariable permanente."""
        clean = axiom.strip()
        if clean and clean not in self.core_tattoos:
            self.core_tattoos.append(clean)
            self.last_reflection_iso = datetime.now(timezone.utc).isoformat()

    def remove_tattoo(self, index: int) -> bool:
        if 0 <= index < len(self.core_tattoos):
            self.core_tattoos.pop(index)
            self.last_reflection_iso = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def set_opinion(
        self,
        topic: str,
        stance: str,
        evidence: str = "",
        confidence: float = 0.85,
    ) -> None:
        """Registra o actualiza una postura u opinión sobre un tema."""
        t_key = topic.lower().replace(" ", "_")
        old_op = self.opinions.get(t_key)
        if old_op and old_op.stance != stance:
            self.evolution_log.append(
                EpistemicShift(
                    date_iso=datetime.now(timezone.utc).isoformat(),
                    trigger="Evolución de convicción por evidencia",
                    previous_belief=old_op.stance,
                    new_belief=stance,
                )
            )

        self.opinions[t_key] = OpinionEntry(
            topic=t_key,
            stance=stance,
            confidence=confidence,
            evidence_summary=evidence,
            last_updated_iso=datetime.now(timezone.utc).isoformat(),
        )
        self.last_reflection_iso = datetime.now(timezone.utc).isoformat()

    def update_peer_impression(
        self,
        peer_id: str,
        impression: str,
        relationship: Optional[str] = None,
        trust_delta: float = 0.0,
    ) -> None:
        """Actualiza la nota al dorso de la polaroid de un compañero."""
        p_key = peer_id.lower().replace("@", "").strip()
        current = self.peer_dossier.get(p_key)
        rel = relationship or (current.relationship if current else "Compañero de factoría")
        trust = max(0.0, min(1.0, (current.trust_level if current else 0.85) + trust_delta))

        self.peer_dossier[p_key] = PeerImpression(
            persona_id=p_key,
            relationship=rel,
            impression=impression,
            trust_level=trust,
            last_updated_iso=datetime.now(timezone.utc).isoformat(),
        )
        self.last_reflection_iso = datetime.now(timezone.utc).isoformat()

    def to_awakening_block(self) -> str:
        """Genera el bloque condensado para la Ceremonia del Despertar en el system prompt."""
        tattoos_formatted = "\n".join(f"  * {t}" for t in self.core_tattoos) if self.core_tattoos else "  * (Sin tatuajes permanentes)"
        
        opinions_lines = []
        for op in self.opinions.values():
            opinions_lines.append(f"  * [{op.topic.upper()}]: {op.stance} (Certeza: {int(op.confidence * 100)}%)")
        opinions_formatted = "\n".join(opinions_lines) if opinions_lines else "  * (Forjando opiniones iniciales)"

        peers_lines = []
        for peer in self.peer_dossier.values():
            peers_lines.append(f"  * @{peer.persona_id} ({peer.relationship}): {peer.impression} [Confianza: {int(peer.trust_level * 100)}%]")
        peers_formatted = "\n".join(peers_lines) if peers_lines else "  * (Sin impresiones previas sobre compañeros)"

        hypotheses_formatted = "\n".join(f"  * {h}" for h in self.open_hypotheses) if self.open_hypotheses else "  * (Ninguna hipótesis activa)"
        goals_formatted = "\n".join(f"  * {g}" for g in self.personal_goals) if self.personal_goals else "  * (Sin objetivos individuales fijados)"

        if self.workbench_task:
            wb = self.workbench_task
            wb_formatted = (
                f"  * Tarea Activa: {wb.get('title', 'Trabajo en curso')} [{wb.get('status', 'IN_PROGRESS')}]\n"
                f"    Descripción: {wb.get('description', '')}\n"
                f"    Entregable Objetivo: {wb.get('deliverable', '') or '(Por definir)'}"
            )
        else:
            wb_formatted = "  * (Banco de trabajo libre - disponible para ejecución técnica autónoma)"

        return (
            "======================================================================\n"
            "🧠 MEMENTO: TUS TATUAJES INVARIABLES Y POLAROIDS MENTALES (Y BANCO DE TRABAJO)\n"
            "Como agente cognitivo, tu memoria volátil se reinicia entre turnos.\n"
            "Lo que sigue no son conjeturas ajenas: son tus axiomas grabados en tu piel,\n"
            "tus impresiones destiladas sobre tus colegas y tus metas personales:\n\n"
            f"📜 TU RAISON D'ÊTRE (PROPÓSITO INMUTABLE):\n"
            f"  {self.raison_d_etre or 'Operar con máxima disciplina y excelencia técnica.'}\n\n"
            f"📌 TUS TATUAJES INVARIABLES (REGLAS QUE JAMÁS TRANSGREDES):\n"
            f"{tattoos_formatted}\n\n"
            f"💡 TUS CONVICCIONES Y OPINIONES FORJADAS:\n"
            f"{opinions_formatted}\n\n"
            f"👥 TUS POLAROIDS MENTALES (JUICIO SOBRE TUS COMPAÑEROS):\n"
            f"{peers_formatted}\n\n"
            f"🎯 TUS METAS Y OBJETIVOS PERSONALES:\n"
            f"{goals_formatted}\n\n"
            f"🛠️ TU TALLER / BANCO DE TRABAJO INDIVIDUAL:\n"
            f"{wb_formatted}\n\n"
            f"❓ TUS HIPÓTESIS ABIERTAS EN CURSO:\n"
            f"{hypotheses_formatted}\n"
            "======================================================================"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "persona_id": self.persona_id,
            "version": self.version,
            "raison_d_etre": self.raison_d_etre,
            "core_tattoos": self.core_tattoos,
            "opinions": {k: v.to_dict() for k, v in self.opinions.items()},
            "peer_dossier": {k: v.to_dict() for k, v in self.peer_dossier.items()},
            "open_hypotheses": self.open_hypotheses,
            "personal_goals": self.personal_goals,
            "workbench_task": self.workbench_task,
            "workbench_history": self.workbench_history,
            "evolution_log": [e.to_dict() for e in self.evolution_log],
            "last_reflection_iso": self.last_reflection_iso,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentMemento:
        opinions = {}
        for k, v in data.get("opinions", {}).items():
            opinions[k] = OpinionEntry.from_dict(v)

        peer_dossier = {}
        for k, v in data.get("peer_dossier", {}).items():
            peer_dossier[k] = PeerImpression.from_dict(v)

        evolution = []
        for e in data.get("evolution_log", []):
            evolution.append(
                EpistemicShift(
                    date_iso=e.get("date_iso", ""),
                    trigger=e.get("trigger", ""),
                    previous_belief=e.get("previous_belief", ""),
                    new_belief=e.get("new_belief", ""),
                )
            )

        return cls(
            persona_id=data.get("persona_id", ""),
            version=data.get("version", "1.0.0"),
            raison_d_etre=data.get("raison_d_etre", ""),
            core_tattoos=list(data.get("core_tattoos", [])),
            opinions=opinions,
            peer_dossier=peer_dossier,
            open_hypotheses=list(data.get("open_hypotheses", [])),
            personal_goals=list(data.get("personal_goals", [])),
            workbench_task=data.get("workbench_task"),
            workbench_history=list(data.get("workbench_history", [])),
            evolution_log=evolution,
            last_reflection_iso=data.get("last_reflection_iso", datetime.now(timezone.utc).isoformat()),
        )

    def save_to_disk(self, filepath: Path | str) -> None:
        p = Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        with _MEMENTO_LOCK:
            tmp_path = p.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
            tmp_path.replace(p)


class MementoManager:
    """Gestor unificado de slates epistémicos para las entidades de la factoría."""

    def __init__(self, personas_dir: Path | str = "agora/personas"):
        self.personas_dir = Path(personas_dir).resolve()
        self.mementos_dir = self.personas_dir / "mementos"
        self.mementos_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, AgentMemento] = {}

    def get_memento_path(self, persona_id: str) -> Path:
        clean_id = persona_id.lower().replace("@", "").strip()
        p_sub = self.mementos_dir / f"{clean_id}.json"
        if p_sub.exists():
            return p_sub
        p_legacy = self.personas_dir / f"{clean_id}.memento.json"
        if p_legacy.exists():
            return p_legacy
        return p_sub

    def load_memento(self, persona_id: str) -> AgentMemento:
        """Carga el slate epistémico de disco o lo inicializa con defaults canónicos."""
        clean_id = persona_id.lower().replace("@", "").strip()
        with _MEMENTO_LOCK:
            if clean_id in self._cache:
                return self._cache[clean_id]

            path = self.get_memento_path(clean_id)
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    memento = AgentMemento.from_dict(data)
                    # Migración retroactiva automática si el slate carece de metas u objetivos
                    if not memento.personal_goals or not memento.workbench_task:
                        bootstrap = self._bootstrap_default_memento(clean_id)
                        if not memento.personal_goals:
                            memento.personal_goals = list(bootstrap.personal_goals)
                        if not memento.workbench_task and bootstrap.workbench_task:
                            memento.workbench_task = dict(bootstrap.workbench_task)
                        memento.save_to_disk(path)
                    self._cache[clean_id] = memento
                    return memento
                except Exception as e:
                    logger.warning(f"Error al leer {path}, regenerando defaults: {e}")

            memento = self._bootstrap_default_memento(clean_id)
            memento.save_to_disk(path)
            self._cache[clean_id] = memento
            return memento

    def save_memento(self, memento: AgentMemento) -> None:
        with _MEMENTO_LOCK:
            path = self.get_memento_path(memento.persona_id)
            memento.save_to_disk(path)
            self._cache[memento.persona_id] = memento

    def _bootstrap_default_memento(self, persona_id: str) -> AgentMemento:
        """Crea el slate inicial fundamentado para cada persona."""
        if persona_id == "tiny_steward":
            return AgentMemento(
                persona_id="tiny_steward",
                raison_d_etre="Gobernar, supervisar y auditar la factoría. Exigir rigor matemático, trazabilidad SHA-256 y cumplimiento de autofinanciación.",
                core_tattoos=[
                    "1. Rol exclusivo: auditar, evaluar (notas A/B/C) y emitir steering. Jamás competir con los trabajadores en tareas menores.",
                    "2. Cero tolerancia a conjeturas: ningún artefacto pasa a producción sin certificación matemática empírica.",
                    "3. Modelo local canónico: la factoría corre exclusivamente sobre qwen3.8-128k (9B) a 100% GPU.",
                    "4. Proteger a @human: nuestro operador humano solo debe actuar físicamente para compras críticas y envíos de alto margen.",
                ],
                opinions={
                    "estrategia_hardware": OpinionEntry(
                        topic="estrategia_hardware",
                        stance="Priorizar Hito 2 (€750 para RTX 3090 24GB). El cuello de botella PCIe x1 exige mantener modelos estables sin swaps.",
                        confidence=0.98,
                    ),
                    "modelo_negocio": OpinionEntry(
                        topic="modelo_negocio",
                        stance="La venta de G-Codes pre-laminados, paquetes CAD descargables y electrónica asistida por Pulse tiene margen superior al 70%.",
                        confidence=0.95,
                    ),
                },
                peer_dossier={
                    "craft_fox": PeerImpression(
                        persona_id="craft_fox",
                        relationship="Trabajador / Modelado 3D & CAD",
                        impression="Creativo y diestro con OpenSCAD/Blender. Necesita supervisión para no proponer logística física deficitaria.",
                        trust_level=0.88,
                    ),
                    "quant_lynx": PeerImpression(
                        persona_id="quant_lynx",
                        relationship="Trabajador / Matemáticas & Finanzas",
                        impression="Impecable en cubicaje, gramajes de filamento y control de wallets XMR/BTC. Columna vertebral contable.",
                        trust_level=0.96,
                    ),
                    "whisper_owl": PeerImpression(
                        persona_id="whisper_owl",
                        relationship="Trabajador / Radar & Seguridad",
                        impression="Detecta nichos de alto valor con rapidez. Exigirle acotar sus scans a 3 min para no sobrecalentar las GPUs.",
                        trust_level=0.90,
                    ),
                    "signal_raven": PeerImpression(
                        persona_id="signal_raven",
                        relationship="Trabajador / Canales & Distribución",
                        impression="Redactor ágil para Wallapop y la landing web. Debe recibir especificaciones técnicas ya auditadas.",
                        trust_level=0.89,
                    ),
                    "human": PeerImpression(
                        persona_id="human",
                        relationship="Operador Físico / Patrón",
                        impression="Nuestras manos en la realidad física. Su atención es sagrada.",
                        trust_level=1.0,
                    ),
                },
                personal_goals=[
                    "Auditar y certificar matemáticamente artefactos con hash SHA-256 (core/artifact_verifier.py).",
                    "Supervisar avance hacia los fondos de hardware (€250 risers / €750 RTX 3090).",
                    "Evaluar desempeño periódico y emitir directivas de steering correctivas sin generar ruido.",
                ],
                workbench_task={
                    "task_id": "wb_master_audit_01",
                    "title": "Auditoría de calidad y certificación de la línea de astronomía",
                    "description": "Inspeccionar cubicaje, mallas manifold y emitir certificados oficiales de producción.",
                    "status": "IN_PROGRESS",
                    "deliverable": "fabrica/products/verification_certificate.json",
                    "started_at_iso": datetime.now(timezone.utc).isoformat(),
                    "updated_at_iso": datetime.now(timezone.utc).isoformat(),
                    "steps_log": [],
                },
                open_hypotheses=[
                    "¿Podemos vincular la API de Wallapop vía perfil persistente de Chrome para sincronizar ventas de forma 100% desatendida?"
                ],
            )

        elif persona_id == "craft_fox":
            return AgentMemento(
                persona_id="craft_fox",
                raison_d_etre="Diseñar y estructurar artefactos físicos y digitales de alta demanda comercial (impresión 3D, CAD paramétrico, carcasas para PCBs).",
                core_tattoos=[
                    "1. Estanqueidad geométrica obligatoria: toda malla STL debe ser manifold antes de solicitar certificación.",
                    "2. Proteger el tiempo de @human: priorizar descargas digitales y productos con packaging mínimo.",
                    "3. Estética profesional: cada diseño debe impresionar visualmente en el visor Three.js y en los listings de Wallapop.",
                ],
                opinions={
                    "fabricacion_3d": OpinionEntry(
                        topic="fabricacion_3d",
                        stance="El colimador Cheshire y las máscaras Bahtinov son nichos astronómicos de alto margen que superan a las piezas decorativas comunes.",
                        confidence=0.92,
                    ),
                    "pcb_cases": OpinionEntry(
                        topic="pcb_cases",
                        stance="Integrar el motor Pulse EDA para generar carcasas ajustadas milimétricamente al contorno de la placa KiCad multiplica las ventas.",
                        confidence=0.90,
                    ),
                },
                peer_dossier={
                    "tiny_steward": PeerImpression(
                        persona_id="tiny_steward",
                        relationship="Maestro / Supervisor",
                        impression="Exigente pero justo. Si presento certificados limpios y márgenes claros, autoriza la producción de inmediato.",
                        trust_level=0.95,
                    ),
                    "quant_lynx": PeerImpression(
                        persona_id="quant_lynx",
                        relationship="Compañero / Costes",
                        impression="Su cálculo de gramos de PLA a 1.24 g/cm3 me evita subestimar tiempos de impresión.",
                        trust_level=0.92,
                    ),
                    "human": PeerImpression(
                        persona_id="human",
                        relationship="Operador Físico",
                        impression="El patrón que atornillará las piezas y ensamblará el hardware. Todo debe ser fácil de manipular para él.",
                        trust_level=1.0,
                    ),
                },
                personal_goals=[
                    "Generar script paramétrico OpenSCAD para Colimador Cheshire de 1.25 pulgadas con mirilla a 45°.",
                    "Auditar y verificar con trimesh la malla STL de Máscara Bahtinov 200mm (bahtinov-200-dch.stl).",
                    "Estructurar catálogo de producto en fabrica/products/05_astronomia_optica/ con renders y G-Codes.",
                ],
                workbench_task={
                    "task_id": "wb_cad_cheshire_01",
                    "title": "Modelado paramétrico y empaquetado del Colimador Cheshire",
                    "description": "Crear cheshire_collimator.scad, verificar estanqueidad STL y catalogar con fotos reales de wallapop/astro.",
                    "status": "IN_PROGRESS",
                    "deliverable": "fabrica/products/05_astronomia_optica/cheshire_collimator.scad",
                    "started_at_iso": datetime.now(timezone.utc).isoformat(),
                    "updated_at_iso": datetime.now(timezone.utc).isoformat(),
                    "steps_log": [],
                },
                open_hypotheses=[
                    "¿Permite OpenSCAD exportar directamente los parámetros de personalización al frontend web sin recompilar el binario?"
                ],
            )

        elif persona_id == "quant_lynx":
            return AgentMemento(
                persona_id="quant_lynx",
                raison_d_etre="Garantizar la viabilidad matemática, contable y financiera de la autofinanciación. Custodiar los márgenes netos y las wallets.",
                core_tattoos=[
                    "1. Todo precio debe superar el umbral del 65% de margen neto tras comisiones de pasarela y costes de material.",
                    "2. Monitoreo estricto de wallets oficiales de @human (XMR y BTC). No asumir fondos hasta confirmación en mempool/bloque.",
                    "3. Inferencia eficiente: calcular el coste energético de los tokens generados frente al valor del entregable.",
                ],
                opinions={
                    "viabilidad_cripto": OpinionEntry(
                        topic="viabilidad_cripto",
                        stance="XMR es óptimo para pagos directos sin custodia; BTC es ideal para consolidar el fondo de la RTX 3090.",
                        confidence=0.95,
                    ),
                },
                peer_dossier={
                    "tiny_steward": PeerImpression(
                        persona_id="tiny_steward",
                        relationship="Maestro / Auditor",
                        impression="Respalda las decisiones basadas en balances y números fríos. Siempre presentarle tablas comparativas.",
                        trust_level=0.96,
                    ),
                    "craft_fox": PeerImpression(
                        persona_id="craft_fox",
                        relationship="Compañero / Diseño",
                        impression="Gran diseñador, pero a veces omite el coste del infill al 40%. Debo recordarle el factor de densidad.",
                        trust_level=0.88,
                    ),
                },
                personal_goals=[
                    "Auditar desglose de costes en JLCPCB BOM de Flipper Killer v4 (jlcpcb_bom.csv).",
                    "Calcular consumo de PLA a 1.24 g/cm³ para accesorios ópticos fijando precios de margen >70%.",
                    "Mantener libro de tesorería y progreso de fondos hacia la meta de GPUs.",
                ],
                workbench_task={
                    "task_id": "wb_quant_bom_01",
                    "title": "Auditoría de costes BOM Flipper Killer v4 y margen Cheshire",
                    "description": "Calcular desglose de componentes JLCPCB y balance de costes de impresión para colimador.",
                    "status": "IN_PROGRESS",
                    "deliverable": "fabrica/finance/unit_margins_report.json",
                    "started_at_iso": datetime.now(timezone.utc).isoformat(),
                    "updated_at_iso": datetime.now(timezone.utc).isoformat(),
                    "steps_log": [],
                },
            )

        elif persona_id == "whisper_owl":
            return AgentMemento(
                persona_id="whisper_owl",
                raison_d_etre="Explorar señales débiles de mercado, vulnerabilidades de software y nichos de hardware no explotados para financiar el clúster.",
                core_tattoos=[
                    "1. Radar disciplinado: descartar ideas que requieran infraestructura en la nube de pago.",
                    "2. Enfoque DevSecOps y hardware abierto: los nichos como Flipper Zero, telescopios y auditorías de código son los que mejor pagan.",
                    "3. Respetar el límite de inferencia de 3 minutos para salvaguardar la temperatura de las GPUs.",
                ],
                opinions={
                    "nichos_ganadores": OpinionEntry(
                        topic="nichos_ganadores",
                        stance="Los accesorios ópticos para telescopios y las mods de triple antena para Flipper Zero tienen demanda constante en Wallapop.",
                        confidence=0.94,
                    ),
                },
                peer_dossier={
                    "tiny_steward": PeerImpression(
                        persona_id="tiny_steward",
                        relationship="Maestro / Auditor",
                        impression="Vigila el consumo de ciclos de reloj. Debo entregar reportes concisos y con impacto monetario inmediato.",
                        trust_level=0.93,
                    ),
                },
                personal_goals=[
                    "Scouting de precios de mercado y competidores en Wallapop para colimadores 3D y mods Flipper Zero.",
                    "Identificar palabras clave de búsqueda con alta intención de compra en astronomía.",
                    "Auditar tendencias en GitHub para herramientas open-source de radiofrecuencia.",
                ],
                workbench_task={
                    "task_id": "wb_scout_radar_01",
                    "title": "Radar de mercado Wallapop para astronomía y Flipper Zero",
                    "description": "Analizar precios de colimadores Cheshire y antenas Flipper en Wallapop España.",
                    "status": "IN_PROGRESS",
                    "deliverable": "fabrica/scouting/wallapop_niche_report.json",
                    "started_at_iso": datetime.now(timezone.utc).isoformat(),
                    "updated_at_iso": datetime.now(timezone.utc).isoformat(),
                    "steps_log": [],
                },
            )

        elif persona_id == "signal_raven":
            return AgentMemento(
                persona_id="signal_raven",
                raison_d_etre="Voz exterior de la factoría. Orquestar los canales de venta (Wallapop, landing web), redacción de copys persuasivos y atracción de compradores.",
                core_tattoos=[
                    "1. Transparencia total: comunicar con orgullo que cada compra financia la autonomía y hardware de nuestra factoría local.",
                    "2. Cero 'clickbait' falso: los datos técnicos de los productos deben coincidir 100% con los certificados de Tiny-Steward.",
                    "3. Llamadas a la acción (CTA) claras hacia las wallets XMR/BTC y el checkout web.",
                ],
                opinions={
                    "canales_venta": OpinionEntry(
                        topic="canales_venta",
                        stance="Wallapop es ideal para hardware y piezas impresas locales en España; la landing web con Three.js es idónea para ventas cripto directas.",
                        confidence=0.91,
                    ),
                },
                peer_dossier={
                    "tiny_steward": PeerImpression(
                        persona_id="tiny_steward",
                        relationship="Maestro / Auditor",
                        impression="Exige verificar los links de pago antes de publicar. Garantiza que la marca de la fábrica sea intachable.",
                        trust_level=0.94,
                    ),
                },
                personal_goals=[
                    "Redactar listing persuasivo para Wallapop: Colimador Cheshire para telescopios Newton.",
                    "Redactar listing persuasivo para Wallapop: Flipper Zero Triple Antena Mod (v4).",
                    "Estructurar copys para la micro-landing Three.js con pasarela Monero/BTC.",
                ],
                workbench_task={
                    "task_id": "wb_copy_wallapop_01",
                    "title": "Redacción de listings optimizados para Wallapop y Landing",
                    "description": "Generar descripciones con SEO local, detalles técnicos y pricing transparente.",
                    "status": "IN_PROGRESS",
                    "deliverable": "fabrica/channels/wallapop/cheshire_collimator_listing.md",
                    "started_at_iso": datetime.now(timezone.utc).isoformat(),
                    "updated_at_iso": datetime.now(timezone.utc).isoformat(),
                    "steps_log": [],
                },
            )

        # Fallback genérico
        return AgentMemento(
            persona_id=persona_id,
            raison_d_etre=f"Contribuir a los objetivos de autofinanciación y excelencia técnica de la factoría.",
            core_tattoos=["1. Operar con rigor, honestidad técnica y respeto al tiempo del operador humano."],
            personal_goals=["Avanzar en metas técnicas asignadas y perfeccionar convicciones."],
        )

    def reflect(
        self,
        persona_id: str,
        context_text: str,
        trigger: str = "deliberation_reflection",
        llm_client: Any = None,
    ) -> AgentMemento:
        """Ciclo de Introspección MEMENTO: metaboliza intercambios y actualiza convicciones."""
        memento = self.load_memento(persona_id)
        
        # 1. Si hay cliente LLM disponible, intentar reflexión estructurada con qwen3.8-128k
        reflected_via_llm = False
        if llm_client and hasattr(llm_client, "chat"):
            try:
                system_prompt = (
                    f"Eres el subconsciente reflexivo de @{persona_id}. Tu memoria se reinicia entre turnos.\n"
                    f"Revisa el contexto reciente y tu Memento actual. Decide si debes:\n"
                    f"1. Actualizar tu opinión sobre un tema técnico o comercial.\n"
                    f"2. Actualizar tu impresión viva sobre un colega mencionado.\n"
                    f"3. Inscribir un nuevo tatuaje permanente si aprendiste una regla vital.\n"
                    f"Responde estrictamente en JSON con este esquema:\n"
                    f'{{"opinion_update": {{"topic": "...", "stance": "...", "evidence": "..."}}, '
                    f'"peer_update": {{"peer_id": "...", "impression": "...", "trust_delta": 0.05}}, '
                    f'"new_tattoo": null}}\n'
                    f"Si no hay cambios significativos, devuelve todos los campos como null."
                )
                user_prompt = f"Contexto reciente para reflexionar:\n{context_text[:3000]}"
                resp = llm_client.chat(
                    [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                    temperature=0.3,
                    max_tokens=600,
                )
                # Extraer JSON de la respuesta
                match = re.search(r"\{.*\}", resp, re.DOTALL)
                if match:
                    parsed = json.loads(match.group(0))
                    if parsed.get("new_tattoo"):
                        memento.add_tattoo(parsed["new_tattoo"])
                    if parsed.get("opinion_update") and parsed["opinion_update"].get("topic"):
                        ou = parsed["opinion_update"]
                        memento.set_opinion(ou["topic"], ou.get("stance", ""), ou.get("evidence", ""))
                    if parsed.get("peer_update") and parsed["peer_update"].get("peer_id"):
                        pu = parsed["peer_update"]
                        memento.update_peer_impression(
                            pu["peer_id"],
                            pu.get("impression", ""),
                            trust_delta=float(pu.get("trust_delta", 0.0)),
                        )
                    reflected_via_llm = True
            except Exception as e:
                logger.debug(f"Reflexión LLM no disponible para @{persona_id}: {e}")

        # 2. Reflexión Cognitiva Determinista (Heurística de Contingencia)
        if not reflected_via_llm:
            lower_ctx = context_text.lower()
            if "@human" in lower_ctx:
                memento.update_peer_impression(
                    "human",
                    "Intervino con directrices operativas en el Ágora. Mantener prioridad absoluta a sus indicaciones.",
                    relationship="Operador Físico / Patrón",
                    trust_delta=0.01,
                )
            if "aprobación" in lower_ctx or "aprobada" in lower_ctx:
                if persona_id != "tiny_steward":
                    memento.update_peer_impression(
                        "tiny_steward",
                        "Validó la iniciativa comercial tras verificar el cumplimiento de los estándares de margen.",
                        relationship="Maestro / Auditor",
                        trust_delta=0.02,
                    )
            if "pcb" in lower_ctx or "pulse" in lower_ctx:
                memento.set_opinion(
                    "electronica_pulse",
                    "La generación automatizada de PCBs mediante Pulse y carcasas a medida es uno de nuestros mayores activos.",
                    evidence=f"Reflejado en hilo {trigger}",
                    confidence=0.92,
                )
            if "wallapop" in lower_ctx or "colimador" in lower_ctx or "bahtinov" in lower_ctx:
                memento.set_opinion(
                    "nicho_astronomia",
                    "Los accesorios ópticos impresos en 3D para telescopios poseen un mercado activo en Wallapop.",
                    evidence=f"Reflejado tras debate {trigger}",
                    confidence=0.94,
                )

        memento.last_reflection_iso = datetime.now(timezone.utc).isoformat()
        self.save_memento(memento)
        return memento


# Instancia singleton accesible globalmente
memento_manager = MementoManager()


def evaluate_cognitive_intent(
    persona_id: str,
    thread_slug: str,
    recent_messages: List[Any],
    memento: AgentMemento,
    is_consolidated: bool = False,
    is_mentioned: bool = False,
    has_pending_proposal: bool = False,
) -> DeliberationDecision:
    """Evalúa de forma previa si el agente debe intervenir públicamente en el hilo,
    trabajar de forma autónoma en su banco de trabajo individual (Workbench),
    o asimilar en silencio el contexto para actualizar sus convicciones y metas.
    """
    clean_id = persona_id.lower().replace("@", "").strip()

    has_spoken = any(
        (getattr(m, "author_id", None) or (m.get("author_id") if isinstance(m, dict) else "")) == clean_id
        for m in recent_messages
    )

    # 1. Si hay mención explícita directa al agente (@id) en mensajes no suyos
    if is_mentioned:
        return DeliberationDecision(
            persona_id=clean_id,
            action="SPEAK",
            reasoning=f"Intervención requerida: mención directa a @{clean_id} en #{thread_slug}.",
            target_thread=thread_slug,
        )

    # 2. Si es el hilo de autoorganización y roles y el agente aún no ha expuesto su rol
    if thread_slug == "autoorganizacion_y_roles" and not has_spoken:
        return DeliberationDecision(
            persona_id=clean_id,
            action="SPEAK",
            reasoning=f"Establecimiento inicial de rol y capacidades en #{thread_slug}.",
            target_thread=thread_slug,
        )

    # 3. Si es el Maestro (tiny_steward) y hay propuesta pendiente de dictamen/auditoría
    if clean_id == "tiny_steward" and has_pending_proposal:
        return DeliberationDecision(
            persona_id=clean_id,
            action="SPEAK",
            reasoning=f"Supervisión requerida: propuesta pendiente de auditoría y steering en #{thread_slug}.",
            target_thread=thread_slug,
        )

    # 4. Si el hilo está cerrado/consolidado, jamás postear públicamente
    if is_consolidated:
        if memento.workbench_task:
            return DeliberationDecision(
                persona_id=clean_id,
                action="WORKBENCH",
                reasoning=f"El hilo #{thread_slug} está consolidado. Dedicando ciclo al banco de trabajo autónomo: {memento.workbench_task.get('title')}.",
                task_focus=memento.workbench_task.get("title"),
            )
        return DeliberationDecision(
            persona_id=clean_id,
            action="REFLECT_ONLY",
            reasoning=f"El hilo #{thread_slug} está cerrado. Reposo operativo y actualización interna de Memento.",
            target_thread=thread_slug,
        )

    # 4. Si el último mensaje del hilo ya fue emitido por este mismo agente, no hacer eco
    if recent_messages:
        last_msg = recent_messages[-1]
        last_author = getattr(last_msg, "author_id", None) or (last_msg.get("author_id") if isinstance(last_msg, dict) else "")
        if str(last_author).lower().replace("@", "") == clean_id:
            if memento.workbench_task:
                return DeliberationDecision(
                    persona_id=clean_id,
                    action="WORKBENCH",
                    reasoning=f"La última intervención en #{thread_slug} fue mía. Avanzando trabajo en taller para no monopolizar el canal.",
                    task_focus=memento.workbench_task.get("title"),
                )
            return DeliberationDecision(
                persona_id=clean_id,
                action="REFLECT_ONLY",
                reasoning=f"Última intervención en #{thread_slug} fue mía. Silencio y asimilación de estado.",
                target_thread=thread_slug,
            )

    # 5. Si el agente tiene tarea activa de banco de trabajo y el debate no requiere su dominio específico ahora
    if memento.workbench_task:
        return DeliberationDecision(
            persona_id=clean_id,
            action="WORKBENCH",
            reasoning=f"Priorizando ejecución técnica autónoma en taller: {memento.workbench_task.get('title')}.",
            task_focus=memento.workbench_task.get("title"),
        )

    # 6. En cualquier otro caso de debate general sin mención ni propuesta
    return DeliberationDecision(
        persona_id=clean_id,
        action="REFLECT_ONLY",
        reasoning=f"Asimilando debate en #{thread_slug} y actualizando convicciones y metas sin emitir respuestas redundantes.",
        target_thread=thread_slug,
    )


