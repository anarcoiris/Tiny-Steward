// Molde y Sello de Precisión Botánica para Modelado — Diseñado por @craft_fox
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
