// Módulo Apilable de Torre Hidropónica Vertical — Diseñado por @craft_fox
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
