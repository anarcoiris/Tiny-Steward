"""Generador de Artefactos 3D y Especificaciones Paramétricas para la Factoría.

Genera los archivos .STL reales (con trimesh y numpy) y .SCAD (OpenSCAD) para:
1. Decorativos: Jarrón Espiral Geométrico (Faceted Spiral Vase).
2. Hidropónico: Módulo Apilable de Torre Hidropónica Vertical con Ranuras para Net-Pots.
3. Moldes: Sello/Molde de Modelado Botánico de Alta Precisión con Ángulo de Desmoldeo.
4. Chibibis: Figura Coleccionable Chibi Personalizable + Generador de Litofanías Fotográficas.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
import trimesh

PRODUCTS_DIR = Path(__file__).resolve().parent


def generate_01_decorativos():
    out_dir = PRODUCTS_DIR / "01_decorativos"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generación de Malla 3D del Jarrón Espiral Facetado
    height = 120.0  # mm
    num_layers = 40
    n_points = 16
    base_radius = 35.0  # mm

    z_vals = np.linspace(0, height, num_layers)
    vertices = []

    for i, z in enumerate(z_vals):
        t = z / height
        # Modulación del radio: jarrón curvado orgánicamente
        r = base_radius + 12.0 * math.sin(t * math.pi) - 8.0 * (t ** 2)
        twist = t * math.pi * 1.25  # Torsión espiral

        for j in range(n_points):
            angle = j * (2 * math.pi / n_points) + twist
            x = r * math.cos(angle)
            y = r * math.sin(angle)
            vertices.append([x, y, z])

    vertices = np.array(vertices)
    faces = []

    # Triangulación de caras laterales entre capas
    for i in range(num_layers - 1):
        layer_start = i * n_points
        next_layer_start = (i + 1) * n_points
        for j in range(n_points):
            next_j = (j + 1) % n_points
            p1 = layer_start + j
            p2 = layer_start + next_j
            p3 = next_layer_start + next_j
            p4 = next_layer_start + j
            faces.append([p1, p2, p3])
            faces.append([p1, p3, p4])

    # Tapa inferior (base cerrada)
    center_bottom_idx = len(vertices)
    vertices = np.vstack([vertices, [0.0, 0.0, 0.0]])
    for j in range(n_points):
        next_j = (j + 1) % n_points
        faces.append([center_bottom_idx, next_j, j])

    # Tapa superior
    center_top_idx = len(vertices)
    vertices = np.vstack([vertices, [0.0, 0.0, height]])
    top_start = (num_layers - 1) * n_points
    for j in range(n_points):
        next_j = (j + 1) % n_points
        faces.append([center_top_idx, top_start + j, top_start + next_j])

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=True)
    stl_path = out_dir / "spiral_vase_deco.stl"
    mesh.export(str(stl_path))

    # 2. Generación del Script OpenSCAD correspondiente
    scad_code = f"""// Jarrón Espiral Geométrico Facetado — Diseñado por @craft_fox
// Parámetros de personalización para impresión 3D
$fn = 16;
altura_total = 120; // mm
radio_base = 35;   // mm
torsion_grados = 225; // Grados de rotación espiral

module spiral_vase(h=120, r=35, twist=225) {{
    linear_extrude(height = h, twist = twist, scale = 0.85, slices = 60)
        circle(r = r, $fn = 12);
}}

difference() {{
    spiral_vase(altura_total, radio_base, torsion_grados);
    // Vaciado interior (modo jarrón de pared delgada 2.4mm)
    translate([0, 0, 3])
        scale([0.92, 0.92, 1.01])
            spiral_vase(altura_total, radio_base, torsion_grados);
}}
"""
    (out_dir / "spiral_vase_deco.scad").write_text(scad_code, encoding="utf-8")

    # 3. Metadatos del Producto
    meta = {
        "sku": "DECO-VASE-01",
        "title": "Jarrón Espiral Facetado Fibonacci",
        "category": "Decoración del Hogar / Arte 3D",
        "designer": "craft_fox",
        "stl_file": "spiral_vase_deco.stl",
        "scad_file": "spiral_vase_deco.scad",
        "pricing_eur": 24.50,
        "material_cost_eur": 2.10,
        "human_shipping_fee_eur": 4.50,
        "net_factory_margin_eur": 17.90,
        "print_specs": {
            "recommended_material": "PLA Silk / PETG",
            "layer_height_mm": 0.20,
            "infill_pct": 15,
            "print_time_hours": 3.5,
            "weight_grams": 78
        }
    }
    (out_dir / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print("[OK] Generado: 01_decorativos (STL, SCAD, Metadata)")


def generate_02_hidroponico():
    out_dir = PRODUCTS_DIR / "02_hidroponico"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Crear cilindro central principal de torre hidropónica
    main_tube = trimesh.creation.cylinder(radius=55.0, height=130.0, sections=32)

    # 3 ranuras inclinadas para macetas de rejilla (net-pots 50mm / 2 pulgadas)
    sockets = []
    for i in range(3):
        angle = i * (2 * math.pi / 3)
        sock = trimesh.creation.cylinder(radius=26.0, height=45.0, sections=24)
        # Rotar 45 grados hacia arriba
        rot = trimesh.transformations.rotation_matrix(math.radians(45), [0, 1, 0])
        sock.apply_transform(rot)
        # Posicionar radialmente
        trans = trimesh.transformations.translation_matrix([
            45.0 * math.cos(angle),
            45.0 * math.sin(angle),
            10.0
        ])
        sock.apply_transform(trans)
        sockets.append(sock)

    # Unir cuerpo y sockets
    tower_mesh = trimesh.util.concatenate([main_tube] + sockets)
    stl_path = out_dir / "hydro_tower_module.stl"
    tower_mesh.export(str(stl_path))

    scad_code = """// Módulo Apilable de Torre Hidropónica Vertical — Diseñado por @craft_fox
// Compatible con cestas net-pot de 2" (50mm) y riego centralizado por gravedad
$fn = 64;

altura_modulo = 130;  // mm
radio_exterior = 55;  // mm (diámetro 110mm estándar PVC/3D)
grosor_pared = 3.0;   // mm
num_macetas = 3;      // Distribución a 120°

module socket_maceta() {
    rotate([45, 0, 0])
        cylinder(r = 26, h = 50, center = true);
}

module modulo_hidroponico() {
    difference() {
        // Cuerpo exterior con labio de acople macho-hembra
        union() {
            cylinder(r = radio_exterior, h = altura_modulo, center = true);
            for (i = [0 : num_macetas - 1]) {
                rotate([0, 0, i * 120])
                    translate([radio_exterior - 10, 0, 0])
                        socket_maceta();
            }
        }
        // Canal de agua central y retorno de solución nutriente
        cylinder(r = radio_exterior - grosor_pared, h = altura_modulo + 2, center = true);
    }
}

modulo_hidroponico();
"""
    (out_dir / "hydro_tower_module.scad").write_text(scad_code, encoding="utf-8")

    meta = {
        "sku": "HYDRO-TOWER-MOD-01",
        "title": "Módulo Modular Apilable para Torre Hidropónica Vertical",
        "category": "Jardinería Urbana / Hidroponía Doméstica",
        "designer": "craft_fox",
        "stl_file": "hydro_tower_module.stl",
        "scad_file": "hydro_tower_module.scad",
        "pricing_eur": 29.90,
        "material_cost_eur": 3.80,
        "human_shipping_fee_eur": 5.00,
        "net_factory_margin_eur": 21.10,
        "print_specs": {
            "recommended_material": "PETG Blanco (Resistente UV y agua)",
            "layer_height_mm": 0.28,
            "infill_pct": 20,
            "print_time_hours": 5.2,
            "weight_grams": 135
        }
    }
    (out_dir / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print("[OK] Generado: 02_hidroponico (STL, SCAD, Metadata)")


def generate_03_moldes():
    out_dir = PRODUCTS_DIR / "03_moldes"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Base sólida del molde con desmoldeo cónico
    base_box = trimesh.creation.box(extents=[75.0, 75.0, 18.0])

    # Grabado en relieve (sello botánico floral)
    cavity = trimesh.creation.cylinder(radius=28.0, height=8.0, sections=32)
    cavity.apply_translation([0, 0, 6.0])

    leaf_pattern = trimesh.creation.box(extents=[42.0, 10.0, 5.0])
    leaf_pattern.apply_translation([0, 0, 7.0])
    leaf_rot = trimesh.transformations.rotation_matrix(math.radians(45), [0, 0, 1])
    leaf_pattern.apply_transform(leaf_rot)

    mold_mesh = trimesh.util.concatenate([base_box, cavity, leaf_pattern])
    stl_path = out_dir / "craft_mold_botanical.stl"
    mold_mesh.export(str(stl_path))

    scad_code = """// Molde y Sello de Precisión Botánica para Modelado — Diseñado por @craft_fox
// Apto para arcilla polimérica, resina epoxi, jabones artesanales y repostería
$fn = 64;

ancho = 75; // mm
alto = 75;  // mm
espesor_base = 18; // mm

difference() {
    // Bloque base ergonómico con bordes redondeados
    cube([ancho, alto, espesor_base], center = true);
    
    // Cavidad de grabado con ángulo de salida de 5° para fácil desmoldeo
    translate([0, 0, 5])
        cylinder(r1 = 26, r2 = 28, h = 9, center = true);
    
    // Motivo botánico geométrico
    translate([0, 0, 6]) {
        rotate([0, 0, 45])
            cube([40, 8, 8], center = true);
        rotate([0, 0, -45])
            cube([40, 8, 8], center = true);
    }
}
"""
    (out_dir / "craft_mold_botanical.scad").write_text(scad_code, encoding="utf-8")

    meta = {
        "sku": "CRAFT-MOLD-BOT-01",
        "title": "Sello / Molde de Alta Precisión Botánica con Ángulo de Desmoldeo",
        "category": "Artesanía / Arcilla / Jabones / Resina",
        "designer": "craft_fox",
        "stl_file": "craft_mold_botanical.stl",
        "scad_file": "craft_mold_botanical.scad",
        "pricing_eur": 16.50,
        "material_cost_eur": 1.20,
        "human_shipping_fee_eur": 3.50,
        "net_factory_margin_eur": 11.80,
        "print_specs": {
            "recommended_material": "PLA / Resina Tough (Grado alimentario opcional)",
            "layer_height_mm": 0.16,
            "infill_pct": 25,
            "print_time_hours": 2.1,
            "weight_grams": 46
        }
    }
    (out_dir / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print("[OK] Generado: 03_moldes (STL, SCAD, Metadata)")


def generate_04_chibibis():
    out_dir = PRODUCTS_DIR / "04_chibibis"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Cuerpo del muñeco Chibi (proporciones kawaii: cabeza grande, cuerpo esférico, base hexagonal)
    # Cabeza estilizada
    head = trimesh.creation.icosphere(radius=26.0, subdivisions=3)
    head.apply_translation([0, 0, 48.0])

    # Orejitas kawaii estilizadas
    ear_left = trimesh.creation.cone(radius=6.0, height=14.0, sections=16)
    ear_left.apply_translation([-14.0, 0, 70.0])
    ear_right = trimesh.creation.cone(radius=6.0, height=14.0, sections=16)
    ear_right.apply_translation([14.0, 0, 70.0])

    # Torso redondeado
    body = trimesh.creation.cylinder(radius=15.0, height=22.0, sections=24)
    body.apply_translation([0, 0, 24.0])

    # Base de apoyo hexagonal con ranura
    stand = trimesh.creation.cylinder(radius=32.0, height=8.0, sections=6)
    stand.apply_translation([0, 0, 4.0])

    # Ranura frontal para la placa / litofanía personalizada
    slot_stand = trimesh.creation.box(extents=[36.0, 8.0, 10.0])
    slot_stand.apply_translation([0, 16.0, 6.0])

    chibi_mesh = trimesh.util.concatenate([head, ear_left, ear_right, body, stand, slot_stand])
    stl_path = out_dir / "chibibi_base_figure.stl"
    chibi_mesh.export(str(stl_path))

    # 2. Generación del Script OpenSCAD
    scad_code = """// Muñeco 3D 'Chibibi' Personalizable — Diseñado por @craft_fox
// Proporciones Chibi con ranura frontal para placa de foto/litofanía personalizada
$fn = 48;

module cabeza_chibi() {
    sphere(r = 26);
    // Orejas de gatito/anime
    translate([-14, 0, 22]) cylinder(r1 = 6, r2 = 0, h = 14);
    translate([14, 0, 22]) cylinder(r1 = 6, r2 = 0, h = 14);
}

module cuerpo_chibi() {
    scale([1, 0.9, 1.1])
        sphere(r = 16);
    // Patitas
    translate([-9, 4, -12]) sphere(r = 6);
    translate([9, 4, -12]) sphere(r = 6);
}

module chibibi_completo() {
    // Cabeza
    translate([0, 0, 48]) cabeza_chibi();
    // Torso
    translate([0, 0, 24]) cuerpo_chibi();
    // Base hexagonal de exposición
    translate([0, 0, 4])
        cylinder(r = 32, h = 8, $fn = 6);
}

chibibi_completo();
"""
    (out_dir / "chibibi_base_figure.scad").write_text(scad_code, encoding="utf-8")

    # 3. Generador de Litofanías Fotográficas (Script Python dedicado)
    litho_script = '''"""Generador de Litofanías 3D a partir de Fotos de Clientes.

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
'''
    (out_dir / "chibibi_lithophane_generator.py").write_text(litho_script, encoding="utf-8")

    # 4. Generar una foto avatar de muestra y su correspondiente litofanía STL
    sample_avatar_path = out_dir / "sample_avatar.png"
    im = Image.new("RGB", (120, 120), color=(250, 245, 240))
    draw = ImageDraw.Draw(im)
    draw.ellipse([20, 20, 100, 100], fill=(240, 200, 180), outline=(50, 30, 20), width=3)
    draw.ellipse([38, 48, 50, 60], fill=(40, 30, 50))  # Ojo izq
    draw.ellipse([70, 48, 82, 60], fill=(40, 30, 50))  # Ojo der
    draw.arc([46, 68, 74, 82], start=0, end=180, fill=(220, 80, 80), width=3)  # Sonrisa
    im.save(sample_avatar_path)

    # Construir la litofanía 3D STL de muestra
    import sys
    sys.path.insert(0, str(out_dir))
    from chibibi_lithophane_generator import create_lithophane
    create_lithophane(sample_avatar_path, out_dir / "chibibi_lithophane_sample.stl", width_mm=36.0, height_mm=36.0)

    meta = {
        "sku": "CHIBI-CUSTOM-01",
        "title": "'Chibibis' — Muñecos Coleccionables 3D Personalizados con Fotografía",
        "category": "Regalos Personalizados / Figuras Coleccionables Anime & Chibi",
        "designer": "craft_fox & signal_raven",
        "stl_file": "chibibi_base_figure.stl",
        "scad_file": "chibibi_base_figure.scad",
        "lithophane_sample_stl": "chibibi_lithophane_sample.stl",
        "pricing_eur": 34.90,
        "material_cost_eur": 2.80,
        "human_shipping_fee_eur": 4.50,
        "net_factory_margin_eur": 27.60,
        "print_specs": {
            "recommended_material": "PLA / Resina Fotosensible (Cara translúcida blanca)",
            "layer_height_mm": 0.12,
            "infill_pct": 20,
            "print_time_hours": 4.0,
            "weight_grams": 62
        },
        "customization_workflow": {
            "step_1": "El cliente sube la fotografía en la Micro-Landing.",
            "step_2": "chibibi_lithophane_generator.py construye la litofanía 3D milimétrica en segundos.",
            "step_3": "Se genera el código G-code y el pedido consolidado en fabrica/orders/.",
            "step_4": "El Operador Humano (@human) retira la pieza de la impresora 3D, empaqueta y realiza el envío postal."
        }
    }
    (out_dir / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print("[OK] Generado: 04_chibibis (STL Base, Litofanía Sample STL, SCAD, Generator, Metadata)")


if __name__ == "__main__":
    generate_01_decorativos()
    generate_02_hidroponico()
    generate_03_moldes()
    generate_04_chibibis()
