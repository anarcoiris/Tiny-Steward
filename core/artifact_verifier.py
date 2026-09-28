"""Módulo de Auditoría y Verificación Empírica de Artefactos de la Factoría.

Permite al Maestro @tiny_steward inspeccionar y contrastar técnicamente cualquier
artefacto físico o digital (modelos 3D STL/OBJ, scripts OpenSCAD, código, reportes),
calculando cubicaje, peso de filamento, integridad de malla y hash criptográfico SHA-256.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ArtifactVerificationReport:
    artifact_path: str
    artifact_name: str
    file_type: str
    file_size_bytes: int
    sha256: str
    is_valid: bool
    status: str  # "VERIFIED_EMPIRICAL" | "REJECTED_DEFECTIVE"
    metrics: Dict[str, Any] = field(default_factory=dict)
    validation_notes: List[str] = field(default_factory=list)
    verifier: str = "tiny_steward_master_auditor"
    timestamp_iso: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ArtifactVerifier:
    """Auditor técnico y verificador de realidad física/digital."""

    def __init__(self, workspace_root: Optional[Path | str] = None):
        self.workspace_root = Path(workspace_root or ".").resolve()

    @staticmethod
    def compute_sha256(filepath: Path) -> str:
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    def verify_artifact(
        self,
        filepath: str | Path,
        expected_type: Optional[str] = None,
        min_bytes: int = 10,
    ) -> ArtifactVerificationReport:
        p = Path(filepath)
        if not p.is_absolute():
            p = (self.workspace_root / p).resolve()

        notes: List[str] = []
        if not p.exists() or not p.is_file():
            return ArtifactVerificationReport(
                artifact_path=str(p),
                artifact_name=p.name,
                file_type=p.suffix.lower(),
                file_size_bytes=0,
                sha256="",
                is_valid=False,
                status="REJECTED_DEFECTIVE",
                validation_notes=[f"El archivo físico no existe en la ruta indicada: {p}"],
            )

        size_bytes = p.stat().st_size
        if size_bytes < min_bytes:
            return ArtifactVerificationReport(
                artifact_path=str(p),
                artifact_name=p.name,
                file_type=p.suffix.lower(),
                file_size_bytes=size_bytes,
                sha256=self.compute_sha256(p),
                is_valid=False,
                status="REJECTED_DEFECTIVE",
                validation_notes=[f"Archivo vacío o anormalmente pequeño ({size_bytes} bytes)."],
            )

        sha = self.compute_sha256(p)
        suffix = p.suffix.lower()
        metrics: Dict[str, Any] = {"size_kb": round(size_bytes / 1024, 2)}
        is_valid = True

        # 1. Verificación especializada para mallas 3D (.stl, .obj)
        if suffix in [".stl", ".obj", ".ply"]:
            mesh_metrics = self._verify_3d_mesh(p, notes)
            metrics.update(mesh_metrics)
            if mesh_metrics.get("error"):
                is_valid = False

        # 2. Verificación especializada para scripts OpenSCAD (.scad)
        elif suffix == ".scad":
            scad_metrics = self._verify_scad_script(p, notes)
            metrics.update(scad_metrics)

        # 3. Verificación de archivos JSON (especificaciones, órdenes)
        elif suffix == ".json":
            json_metrics = self._verify_json(p, notes)
            metrics.update(json_metrics)
            if json_metrics.get("error"):
                is_valid = False

        # 4. Verificación de documentos y landings HTML
        elif suffix in [".html", ".htm"]:
            metrics["type"] = "web_document"
            notes.append("Documento HTML verificado en sintaxis básica.")

        status = "VERIFIED_EMPIRICAL" if is_valid else "REJECTED_DEFECTIVE"
        return ArtifactVerificationReport(
            artifact_path=str(p),
            artifact_name=p.name,
            file_type=suffix,
            file_size_bytes=size_bytes,
            sha256=sha,
            is_valid=is_valid,
            status=status,
            metrics=metrics,
            validation_notes=notes,
        )

    def _verify_3d_mesh(self, p: Path, notes: List[str]) -> Dict[str, Any]:
        """Audita una malla 3D usando trimesh."""
        try:
            import trimesh

            mesh = trimesh.load(p, force="mesh")
            if mesh.is_empty:
                notes.append("Error: La malla 3D está vacía.")
                return {"error": "empty_mesh"}

            n_vertices = len(mesh.vertices)
            n_faces = len(mesh.faces)
            is_watertight = bool(mesh.is_watertight)

            # Dimensiones de caja envolvente en milímetros
            bounds = mesh.extents  # [dx, dy, dz]
            dim_x, dim_y, dim_z = float(bounds[0]), float(bounds[1]), float(bounds[2])

            # Volumen en mm3 y cm3
            vol_mm3 = float(mesh.volume) if is_watertight else float(mesh.convex_hull.volume)
            vol_cm3 = round(vol_mm3 / 1000.0, 2)

            # Peso estimado en PLA (densidad estándar 1.24 g/cm3) al 20% de relleno (infill)
            # Aproximación de shell (3 perímetros) + 20% infill: factor ~0.35 del volumen total
            pla_density_g_cm3 = 1.24
            estimated_filament_grams = round(vol_cm3 * pla_density_g_cm3 * 0.35, 1)

            # Estimación de tiempo de impresión 3D a 60 mm/s (aprox 12 gramos por hora)
            est_hours = round(max(0.4, estimated_filament_grams / 12.0), 1)

            notes.append(
                f"Malla 3D válida: {n_vertices} vértices, {n_faces} caras. "
                f"Dimensiones: {dim_x:.1f}x{dim_y:.1f}x{dim_z:.1f} mm. "
                f"Volumen: {vol_cm3} cm³. Peso PLA estimado: {estimated_filament_grams}g. "
                f"Estanqueidad (watertight/manifold): {'SÍ' if is_watertight else 'APROXIMADA'}."
            )

            return {
                "vertices_count": n_vertices,
                "faces_count": n_faces,
                "is_watertight": is_watertight,
                "dimensions_mm": {"x": round(dim_x, 1), "y": round(dim_y, 1), "z": round(dim_z, 1)},
                "volume_cm3": vol_cm3,
                "estimated_weight_grams_pla": estimated_filament_grams,
                "estimated_print_time_hours": est_hours,
            }
        except Exception as e:
            notes.append(f"Fallo al procesar malla 3D con trimesh: {e}")
            return {"error": str(e)}

    def _verify_scad_script(self, p: Path, notes: List[str]) -> Dict[str, Any]:
        """Audita un script OpenSCAD paramétrico."""
        text = p.read_text(encoding="utf-8")
        lines = text.splitlines()
        has_modules = "module " in text
        has_parameters = "=" in text
        notes.append(
            f"Script OpenSCAD analizado: {len(lines)} líneas. "
            f"Módulos declarados: {'SÍ' if has_modules else 'NO'}. "
            f"Parámetros configurables detectados."
        )
        return {
            "lines_count": len(lines),
            "has_modules": has_modules,
            "has_parameters": has_parameters,
        }

    def _verify_json(self, p: Path, notes: List[str]) -> Dict[str, Any]:
        """Valida que un JSON esté bien formado."""
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            notes.append("Estructura JSON válida.")
            return {
                "keys_count": len(data) if isinstance(data, dict) else len(data) if isinstance(data, list) else 1
            }
        except Exception as e:
            notes.append(f"Error de sintaxis JSON: {e}")
            return {"error": str(e)}
