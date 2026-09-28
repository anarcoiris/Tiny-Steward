// Muñeco 3D 'Chibibi' Personalizable — Diseñado por @craft_fox
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
