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


import difflib
from pathlib import Path


def dif_unificado(
    ruta_archivo_a: str,
    ruta_archivo_b: str,
    contexto: int = 3,
) -> list[str]:
    """Generar un unified diff entre dos archivos.

    Args:
        ruta_archivo_a: Ruta al archivo original (antes).
        ruta_archivo_b: Ruta al archivo modificado (después).
        contexto: Número de líneas de contexto alrededor de cada cambio.

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
    dif = difflib.unified_diff(
        contenido_a,
        contenido_b,
        fromfile=f"archivo_a",
        tofile=f"archivo_b",
        lineterm="",
        n=contexto,
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

    # block_size() fue eliminado en Python 3.10+, usamos ratio() como alternativa
    estadisticas = {
        "lineas_archivo_a": len(contenido_a),
        "lineas_archivo_b": len(contenido_b),
        "similitud_secuencial": round(100 * dif.ratio(), 2),
    }

    # Calcular el bloque más grande idéntico y estadísticas mediante opcodes
    opcodes = dif.get_opcodes()
    max_block = 0
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            max_block = max(max_block, j2 - j1)
    estadisticas["bloque_identico_maximo"] = max_block

    # Contar líneas agregadas, eliminadas y comunes
    agregados = sum(j2 - j1 for tag, i1, i2, j1, j2 in opcodes if tag in ("insert", "replace"))
    eliminados = sum(i2 - i1 for tag, i1, i2, j1, j2 in opcodes if tag in ("delete", "replace"))
    comunes = sum(j2 - j1 for tag, i1, i2, j1, j2 in opcodes if tag == "equal")

    estadisticas["lineas_agregadas"] = agregados
    estadisticas["lineas_eliminadas"] = eliminados
    estadisticas["lineas_comunes"] = comunes

    return estadisticas


def dif_lado_al_lado(
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
        with open(ruta_archivo_a, "r", encoding="utf-8", errors="replace") as f:
            contenido_a = [linea.rstrip("\r\n") for linea in f.readlines()]
    except FileNotFoundError:
        return ["Error: archivo A no encontrado."]

    try:
        with open(ruta_archivo_b, "r", encoding="utf-8", errors="replace") as f:
            contenido_b = [linea.rstrip("\r\n") for linea in f.readlines()]
    except FileNotFoundError:
        return ["Error: archivo B no encontrado."]

    matcher = difflib.SequenceMatcher(None, contenido_a, contenido_b)
    lineas = []
    w_a = max(20, ancho_columna_a)
    w_b = max(20, ancho_columna_b)

    header = f"{'ARCHIVO A (' + Path(ruta_archivo_a).name + ')':<{w_a}} | {'ARCHIVO B (' + Path(ruta_archivo_b).name + ')':<{w_b}}"
    separator = f"{'-' * w_a}-+-{'-' * w_b}"
    lineas.append(header)
    lineas.append(separator)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for a, b in zip(contenido_a[i1:i2], contenido_b[j1:j2]):
                lineas.append(f"  {a[:w_a-2]:<{w_a-2}} |   {b[:w_b-2]:<{w_b-2}}")
        elif tag == "replace":
            a_slice = contenido_a[i1:i2]
            b_slice = contenido_b[j1:j2]
            max_len = max(len(a_slice), len(b_slice))
            for idx in range(max_len):
                a_val = a_slice[idx] if idx < len(a_slice) else ""
                b_val = b_slice[idx] if idx < len(b_slice) else ""
                lineas.append(f"* {a_val[:w_a-2]:<{w_a-2}} | * {b_val[:w_b-2]:<{w_b-2}}")
        elif tag == "delete":
            for a in contenido_a[i1:i2]:
                lineas.append(f"- {a[:w_a-2]:<{w_a-2}} |   {'' :<{w_b-2}}")
        elif tag == "insert":
            for b in contenido_b[j1:j2]:
                lineas.append(f"  {'' :<{w_a-2}} | + {b[:w_b-2]:<{w_b-2}}")

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