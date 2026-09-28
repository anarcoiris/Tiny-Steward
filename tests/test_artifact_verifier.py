"""Tests unitarios para el Auditor de Artefactos y Verificación Empírica."""

from pathlib import Path
import pytest
from core.artifact_verifier import ArtifactVerifier


def test_artifact_verifier_nonexistent_file(tmp_path: Path):
    verifier = ArtifactVerifier(workspace_root=tmp_path)
    report = verifier.verify_artifact(tmp_path / "phantom_model.stl")
    assert not report.is_valid
    assert report.status == "REJECTED_DEFECTIVE"
    assert "no existe" in report.validation_notes[0]


def test_artifact_verifier_real_3d_products():
    verifier = ArtifactVerifier()
    test_paths = [
        "fabrica/products/01_decorativos/spiral_vase_deco.stl",
        "fabrica/products/01_decorativos/spiral_vase_deco.scad",
        "fabrica/products/02_hidroponico/hydro_tower_module.stl",
        "fabrica/products/03_moldes/craft_mold_botanical.stl",
        "fabrica/products/04_chibibis/chibibi_base_figure.stl",
    ]
    for rel_path in test_paths:
        p = Path(rel_path)
        if not p.exists():
            continue
        report = verifier.verify_artifact(p)
        assert report.is_valid
        assert report.status == "VERIFIED_EMPIRICAL"
        assert len(report.sha256) == 64
        if p.suffix == ".stl":
            assert report.metrics["vertices_count"] > 0
            assert report.metrics["faces_count"] > 0
            assert report.metrics["volume_cm3"] > 0
            assert report.metrics["estimated_weight_grams_pla"] > 0
