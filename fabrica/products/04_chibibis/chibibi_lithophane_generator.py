"""Generador de Litofanías 3D a partir de Fotos de Clientes.

Transforma los píxeles de una fotografía en un relieve milimétrico translúcido (0.8mm a 3.0mm)
que se monta directamente en la base o rostro del 'Chibibi'.
"""

from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
from PIL import Image
import trimesh


def create_lithophane(
    image_path: str | Path,
    output_stl_path: str | Path,
    width_mm: float = 40.0,
    height_mm: float = 40.0,
    min_thickness_mm: float = 0.8,
    max_thickness_mm: float = 2.8,
    pixels_w: int = 80,
    pixels_h: int = 80,
) -> Path:
    img = Image.open(image_path).convert("L")  # Escala de grises
    img = img.resize((pixels_w, pixels_h), Image.Resampling.LANCZOS)
    arr = np.array(img, dtype=float)

    # Invertir: lo oscuro debe ser más grueso para bloquear la luz; lo blanco, más delgado
    normalized = 1.0 - (arr / 255.0)
    thickness = min_thickness_mm + normalized * (max_thickness_mm - min_thickness_mm)

    x_lin = np.linspace(-width_mm / 2, width_mm / 2, pixels_w)
    y_lin = np.linspace(height_mm / 2, -height_mm / 2, pixels_h)
    xx, yy = np.meshgrid(x_lin, y_lin)

    # Vértices frontales (superficie de relieve)
    v_front = np.stack([xx.flatten(), yy.flatten(), thickness.flatten()], axis=1)
    # Vértices traseros (plano base en z=0)
    v_back = np.stack([xx.flatten(), yy.flatten(), np.zeros_like(thickness).flatten()], axis=1)

    vertices = np.vstack([v_front, v_back])
    n_pts = len(v_front)

    faces = []
    for r in range(pixels_h - 1):
        for c in range(pixels_w - 1):
            i = r * pixels_w + c
            # Cara frontal
            faces.append([i, i + 1, i + pixels_w])
            faces.append([i + 1, i + pixels_w + 1, i + pixels_w])
            # Cara trasera
            bi = n_pts + i
            faces.append([bi, bi + pixels_w, bi + 1])
            faces.append([bi + 1, bi + pixels_w, bi + pixels_w + 1])

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=True)
    out_p = Path(output_stl_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(str(out_p))
    return out_p


if __name__ == "__main__":
    # Generar litofanía de demostración si se ejecuta directamente
    sample_img = Path("sample_avatar.png")
    if not sample_img.exists():
        im = Image.new("L", (100, 100), color=255)
        im.save(sample_img)
    create_lithophane(sample_img, "chibibi_litho_sample.stl")
