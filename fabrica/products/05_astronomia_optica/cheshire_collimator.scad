// Colimador Cheshire 1.25" Parametrico para Telescopios Newton y Schmidt-Cassegrain
// Disenado por Craft-Fox para Fabrica Tiny Steward (G-Code & STL Manifold)

$fn = 100;

barrel_od = 31.75;       // Diametro exterior estandar de portaocular 1.25 pulgadas
barrel_length = 65.0;    // Longitud total del barril de insercion
wall_thickness = 2.4;    // Grosor de pared para rigidez mecanica
sight_hole_d = 4.2;      // Diametro de mirilla central de observacion
window_w = 20.0;         // Ancho de la ventana de iluminacion a 45 grados
window_h = 24.0;         // Alto de la ventana de iluminacion
flange_od = 36.5;        // Valona o tope de tope superior
flange_h = 8.0;          // Altura de la valona estriada
crosshair_notch = 1.0;   // Ranuras para hilos de reticulo en cruz

module cheshire_body() {
    difference() {
        union() {
            // Barril inferior
            cylinder(d=barrel_od, h=barrel_length);
            // Valona superior
            translate([0, 0, barrel_length - flange_h])
                cylinder(d=flange_od, h=flange_h);
        }
        
        // Tubo hueco interior
        translate([0, 0, -1])
            cylinder(d=barrel_od - 2*wall_thickness, h=barrel_length - 4);
            
        // Mirilla superior
        translate([0, 0, barrel_length - 5])
            cylinder(d=sight_hole_d, h=10);
            
        // Ventana lateral para iluminacion del espejo a 45 grados
        translate([-window_w/2, -barrel_od, barrel_length/2 - window_h/2])
            cube([window_w, barrel_od * 2, window_h]);
            
        // Ranuras cruzadas para reticulo en la base
        translate([-barrel_od/2, -crosshair_notch/2, -0.5])
            cube([barrel_od, crosshair_notch, 3]);
        translate([-crosshair_notch/2, -barrel_od/2, -0.5])
            cube([crosshair_notch, barrel_od, 3]);
    }
}

// Superficie reflectante eliptica interna a 45 grados
module internal_reflector_plate() {
    translate([0, 0, barrel_length/2])
    rotate([45, 0, 0])
    difference() {
        cylinder(d=barrel_od - 2*wall_thickness - 0.5, h=1.8, center=true);
        cylinder(d=sight_hole_d + 1.5, h=10, center=true);
    }
}

union() {
    cheshire_body();
    // Insercion de soporte para reflectante
    translate([0, 0, 0]) internal_reflector_plate();
}
