// Jarrón Espiral Geométrico Facetado — Diseñado por @craft_fox
// Parámetros de personalización para impresión 3D
$fn = 16;
altura_total = 120; // mm
radio_base = 35;   // mm
torsion_grados = 225; // Grados de rotación espiral

module spiral_vase(h=120, r=35, twist=225) {
    linear_extrude(height = h, twist = twist, scale = 0.85, slices = 60)
        circle(r = r, $fn = 12);
}

difference() {
    spiral_vase(altura_total, radio_base, torsion_grados);
    // Vaciado interior (modo jarrón de pared delgada 2.4mm)
    translate([0, 0, 3])
        scale([0.92, 0.92, 1.01])
            spiral_vase(altura_total, radio_base, torsion_grados);
}
