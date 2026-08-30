#!/usr/bin/env python3
"""Visualizador de diferencias entre archivos (dif).

Genera una representación visual de las diferencias entre dos archivos:
- Diffs lado a lado (side-by-side)
- Unificado (unified diff con contexto)
- Resumen estadístico de cambios

Ejemplo:
    from diff_visualizer import dif_unificado, resumen_dif

    resultado = dif_unificado("archivo_v1.txt", "archivo_v2.txt")
    print(resultado)
"""


def dif_unificado(
    ruta_archivo_a: str,
    ruta_archivo_b: str,
    contexto: int = 3,
    max_líneas: int | None = None
) -> list[str]:
    """Generar un unified diff entre dos archivos.

    Args:
        ruta_archivo_a: Ruta al archivo original (antes).
        ruta_archivo_b: Ruta al archivo modificado (después).
        contexto: Número de líneas de contexto alrededor de cada cambio.
        max_líneas: Límite máximo de líneas a mostrar en el diff.

    Returns:
        Lista de strings con la representación del diff.
    """
    import difflib

    try:
        with open(ruta_archivo_a, "r", encoding="utf-8") as f:
            contenido_a = [linea.rstrip("\n") for linea in f.readlines()]
    except FileNotFoundError:
        return ["Error: archivo A no encontrado."]

    try:
        with open(ruta_archivo_b, "r", encoding="utf-8") as f:
            contenido_b = [linea.rstrip("\n") for linea in f.readlines()]
    except FileNotFoundError:
        return ["Error: archivo B no encontrado."]

    # Generar diff unificado con difflib
    dif = difflib.UnifiedDiff(
        fromfile=f"archivo_a",
        tofile=f"archivo_b",
        fromlines=contenido_a,
        tolines=contenido_b,
        lineterm="",
        context=contexto,
        n=max_líneas if max_líneas else None,  # difflib no acepta None aquí
    )

    return list(dif)


def resumen_dif(
    ruta_archivo_a: str,
    ruta_archivo_b: str,
) -> dict[str, int]:
    """Obtener un resumen estadístico de las diferencias entre dos archivos.

    Args:
        ruta_archivo_a: Ruta al archivo original.
        ruta_archivo_b: Ruta al archivo modificado.

    Returns:
        Diccionario con estadísticas: lineas_agregadas, lineas_eliminadas,
        lineas_modificadas, porcentaje_de_cambio, etc.
    """
    import difflib
    import os

    try:
        with open(ruta_archivo_a, "r", encoding="utf-8") as f:
            contenido_a = [linea.rstrip("\n") for linea in f.readlines()]
    except FileNotFoundError:
        return {"error": "Archivo A no encontrado."}

    try:
        with open(ruta_archivo_b, "r", encoding="utf-8") as f:
            contenido_b = [linea.rstrip("\n") for linea in f.readlines()]
    except FileNotFoundError:
        return {"error": "Archivo B no encontrado."}

    # Contar agregados y eliminados usando difflib
    dif = difflib.SequenceMatcher(None, contenido_a, contenido_b)

    estadisticas = {
        "lineas_archivo_a": len(contenido_a),
        "lineas_archivo_b": len(contenido_b),
        "bloque_identico": dif.block_size(),  # tamaño del bloque más grande idéntico
        "similitud_secuencial": round(100 * dif.ratio(), 2),
    }

    # Contar líneas agregadas y eliminadas aproximadamente
    agregados = sum(1 for op, texto in zip(dif.opcodes, contenido_b) if op == dif.INSERT)
    eliminados = sum(1 for op, texto in zip(dif.opcodes, contenido_a) if op == dif.DELETE)

    estadisticas["lineas_agregadas"] = agregados
    estadisticas["lineas_eliminadas"] = eliminados
    estadisticas["lineas_comunes"] = sum(1 for op, _ in zip(dif.opcodes, contenido_b) if op == dif.EQUAL)

    return estadisticas


def dif_lado_al lado(
    ruta_archivo_a: str,
    ruta_archivo_b: str,
    ancho_columna_a: int = 40,
    ancho_columna_b: int = 40
) -> list[str]:
    """Generar un diff lado a lado (side-by-side).

    Args:
        ruta_archivo_a: Archivo original.
        ruta_archivo_b: Archivo modificado.
        ancho_columna_a: Ancho de la columna del archivo A.
        ancho_columna_b: Ancho de la columna del archivo B.

    Returns:
        Lista de strings con el diff lado a lado.
    """
    import difflib

    try:
        with open(ruta_archivo_a, "r", encoding="utf-8") as f:
            contenido_a = [linea.rstrip("\n") for linea in f.readlines()]
    except FileNotFoundError:
        return ["Error: archivo A no encontrado."]

    try:
        with open(ruta_archivo_b, "r", encoding="utf-8") as f:
            contenido_b = [linea.rstrip("\n") for linea in f.readlines()]
    except FileNotFoundError:
        return ["Error: archivo B no encontrado."]

    # Generar diff unificado para obtener las operaciones
    dif = difflib.UnifiedDiff(
        fromfile="archivo_a",
        tofile="archivo_b",
        fromlines=contenido_a,
        tolines=contenido_b,
        lineterm="",
    )

    lineas = []
    ancho_total = max(ancho_columna_a + 30, ancho_columna_b + 30)

    for tag, a_line, b_line in dif:
        if tag == "equal":
            linea = f"{' ' * ancho_columna_a}{a_line:<{ancho_columna_a}}{' ' * 12}{b_line}"
        elif tag == "delete":
            linea = f"{tag} {a_line:<{ancho_columna_a}}{' ' * (ancho_total - len(linea))}"
        else:  # insert
            linea = f"+ {b_line:<{ancho_columna_b}}"

        lineas.append(linea)

    return lineas


def comparar_directorios(
    ruta_dir_a: str,
    ruta_dir_b: str,
    recursivo: bool = True,
) -> dict[str, list[tuple]]:
    """Comparar dos directorios y listar archivos diferentes.

    Args:
        ruta_dir_a: Ruta del primer directorio.
        ruta_dir_b: Ruta del segundo directorio.
        recursivo: Si True, comparar subdirectorios también.

    Returns:
        Diccionario con:
            - "nuevos": archivos nuevos en B
            - "eliminados": archivos eliminados en A
            - "modificados": archivos cambiantes (con resumen del diff)
    """
    import os

    resultados = {
        "nuevos": [],
        "eliminados": [],
        "comunes": [],
        "modificados": [],
    }

    try:
        items_a = set(os.listdir(ruta_dir_a)) if recursivo else set()
    except PermissionError:
        return {"error": f"No se puede leer {ruta_dir_a}"}

    try:
        items_b = set(os.listdir(ruta_dir_b)) if recursivo else set()
    except PermissionError:
        return {"error": f"No se puede leer {ruta_dir_b}"}

    # Filtrar archivos (no directorios)
    archivos_a = set(n for n in items_a if os.path.isfile(os.path.join(ruta_dir_a, n)))
    archivos_b = set(n for n in items_b if os.path.isfile(os.path.join(ruta_dir_b, n)))

    resultados["nuevos"] = list(archivos_b - archivos_a)
    resultados["eliminados"] = list(archivos_a - archivos_b)
    resultados["comunes"] = list(archivos_a & archivos_b)

    # Comparar los comunes
    for nombre in resultados["comunes"]:
        try:
            with open(os.path.join(ruta_dir_a, nombre), "rb") as f_a:
                contenido_a = f_a.read()
            with open(os.path.join(ruta_dir_b, nombre), "rb") as f_b:
                contenido_b = f_b.read()

            if contenido_a != contenido_b:
                resultados["modificados"].append({
                    "nombre": nombre,
                    "tamanio_a": len(contenido_a),
                    "tamanio_b": len(contenido_b),
                })
        except (IOError, OSError):
            pass

    return resultados


if __name__ == "__main__":
    import os

    # Demostración con archivos del sistema actual
    archivo_a = "skills/ejercicios/file_tree_generator.py"
    archivo_b = "skills/ejercicios/diff_visualizer.py"

    if os.path.exists(archivo_a) and os.path.exists(archivo_b):
        print("=== DIF VISUALIZADOR ===")
        print()
        resumen = resumen_dif(archivo_a, archivo_b)
        for key, valor in resumen.items():
            if key != "error":
                print(f"  {key}: {valor}")

    print()
    print("=== RESUMEN DE CAMBIOS ===")
    resultado = comparar_directorios(".", ".")
    if "error" not in resultado:
        print(f"  Nuevos archivos: {len(resultado['nuevos'])}")
        for f in resultado["nuevos"]:
            print(f"    + {f}")

        print(f"\n  Eliminados: {len(resultado['eliminados'])}")
        for f in resultado["eliminados"]:
            print(f"    - {f}")

        print(f"\n  Modificados: {len(resultado['modificados'])}")