#!/usr/bin/env python3
"""Generador de patches (diff/unified) entre archivos.

Crea diffs unificados, patches aplicables y permite comparar
dos versiones del mismo archivo para generar el patch necesario.

También incluye:
- Aplicación de patches a archivos
- Diffs lado a lado visuales
- Resumen estadístico de cambios

Ejemplo:
    from git_patch_generator import generar_patch

    patch = generar_patch("archivo_v1.txt", "archivo_v2.txt")
    print(patch)
"""


import difflib
from pathlib import Path
from typing import Optional


def generar_diff_unificado(
    archivo_a: str,
    archivo_b: str,
    contexto: int = 3,
    num_líneas: Optional[int] = None,
) -> list[str]:
    """Generar un unified diff entre dos archivos.

    Args:
        archivo_a: Archivo original (antes).
        archivo_b: Archivo modificado (después).
        contexto: Líneas de contexto alrededor de cada cambio.
        num_líneas: Límite máximo de líneas en el diff.

    Returns:
        Lista de strings con el formato unified diff.
    """
    with open(archivo_a, "r", encoding="utf-8") as f:
        contenido_a = [linea.rstrip("\n") for linea in f.readlines()]

    with open(archivo_b, "r", encoding="utf-8") as f:
        contenido_b = [linea.rstrip("\n") for linea in f.readlines()]

    dif = difflib.UnifiedDiff(
        fromfile=Path(archivo_a).name,
        tofile=Path(archivo_b).name,
        fromlines=contenido_a,
        tolines=contenido_b,
        lineterm="",
        context=contexto,
        n=num_líneas if num_líneas else None,  # difflib no acepta None aquí
    )

    return list(dif)


def generar_patch(
    archivo_original: str,
    archivo_modificado: str,
    formato: str = "patch",
) -> str:
    """Generar un patch aplicable entre dos archivos.

    Args:
        archivo_original: Archivo original.
        archivo_modificado: Archivo modificado.
        formato: "patch" (unified diff aplicable) o "diff".

    Returns:
        String con el contenido del patch.
    """
    with open(archivo_original, "r", encoding="utf-8") as f:
        contenido_a = [linea.rstrip("\n") for linea in f.readlines()]

    with open(archivo_modificado, "r", encoding="utf-8") as f:
        contenido_b = [linea.rstrip("\n") for linea in f.readlines()]

    dif = difflib.Differ()
    diferencias = list(dif.compare(contenido_a, contenido_b))

    if formato == "patch":
        return _formato_patch(diferencias)
    else:
        return "\n".join(diferencias)


def _formato_patch(
    diferencias: list[str],
) -> str:
    """Convertir una lista de líneas de diff al formato patch.

    El formato patch usa:
        @@ -lineas_originales +lineas_nuevas @@
            contexto
        - línea eliminada
        + línea agregada

    Args:
        diferencias: Lista de strings generada por difflib.Differ().

    Returns:
        String en formato unified diff (patch).
    """
    import re

    lineas_originales = []
    lineas_nuevas = []
    bloques = []
    bloque_actual = []
    indice_original = 0
    indice_nuevo = 0

    for linea in diferencias:
        if linea.startswith(" "):
            # Línea idéntica (contexto)
            bloques[-1][0]["lineas"].append(linea[1:])
            bloque_actual.append(linea[1:])
        elif linea.startswith("-"):
            # Línea eliminada del original
            lineas_originales.append(indice_original)
            indice_original += 1
            if bloques:
                bloques[-1][0]["lineas"].append(linea[1:])
                bloque_actual.append(linea[1:])
        elif linea.startswith("+"):
            # Línea agregada al modificado
            lineas_nuevas.append(indice_nuevo)
            indice_nuevo += 1
            if bloques:
                bloques[-1][0]["lineas"].append(linea[1:])
                bloque_actual.append(linea[1:])

    # Construir el patch
    salida = []
    for bloq in bloques:
        info_original, info_nuevo = bloq[0]

        if lineas_originales and lineas_nuevas:
            salida.append(f"@@ -{lineas_originales[0]}+{lineas_nuevas[0]} @@")
        elif not lineas_originales and lineas_nuevas:
            salida.append(f"@@ -0,0 +1 @@")
        elif lineas_originales and not lineas_nuevas:
            salida.append(f"@@ -1,0 +0 @@")

        for linea in bloque_actual:
            if linea.startswith("-"):
                salida.append(linea[1:])  # eliminar el prefijo '-'
            else:
                salida.append(linea)

    return "\n".join(salida)


def aplicar_patch(
    archivo_destino: str,
    contenido_patch: str,
    crear_archivo: bool = False,
) -> dict[str, any]:
    """Aplicar un patch a un archivo.

    Args:
        archivo_destino: Archivo donde aplicar el patch.
        contenido_patch: String con el contenido del patch.
        crear_archivo: Si True y el archivo no existe, se crea.

    Returns:
        Diccionario con el resultado de la aplicación.
    """
    import re

    lineas = contenido_patch.split("\n")
    archivo_destino_contento = []

    if not Path(archivo_destino).exists() and crear_archivo:
        with open(archivo_destino, "w", encoding="utf-8") as f:
            f.write("")
        archivo_destino_contento = ["" for _ in range(1)]
    else:
        try:
            with open(archivo_destino, "r", encoding="utf-8") as f:
                archivo_destino_contento = [linea.rstrip("\n") for linea in f.readlines()]
        except FileNotFoundError:
            return {"error": f"Archivo no encontrado: {archivo_destino}"}

    # Parsear el patch y aplicar cambios
    lineas_originales = []
    lineas_nuevas = []
    i_original = 0
    i_nuevo = 0

    for linea in lineas:
        if linea.startswith("@@"):
            continue  # saltar encabezado del hunk
        elif linea.startswith("diff "):
            continue  # saltar línea de diff
        elif linea.startswith("---"):
            continue  # saltar archivo original
        elif linea.startswith("+++"):
            continue  # saltar archivo modificado

        if not lineas_originales and i_original == 0:
            lineas_originales.append(i_original)
        if not lineas_nuevas and i_nuevo == 0:
            lineas_nuevas.append(i_nuevo)

        if linea.startswith("-"):
            lineas_originales[-1] = linea[2:]  # reemplazar línea eliminada
            i_original += 1
        elif linea.startswith("+"):
            archivo_destino_contento.insert(i_nuevo, linea[2:])
            i_nuevo += 1
        else:
            if lineas_originales and lineas_nuevas:
                file_index = min(lineas_originales[-1], len(archivo_destino_contento) - 1)
                archivo_destino_contento[file_index] = linea[1:]

    # Escribir el resultado
    with open(archivo_destino, "w", encoding="utf-8") as f:
        for linea in archivo_destino_contento:
            f.write(linea + "\n")

    return {
        "archivos_modificados": [archivo_destino],
        "lineas_agregadas": len([l for l in lineas if l.startswith("+")]) - 1,
        "lineas_eliminadas": len([l for l in lineas if l.startswith("-")]) - 1,
    }


def diff_lado_al lado(
    archivo_a: str,
    archivo_b: str,
    ancho_columna_a: int = 40,
    ancho_columna_b: int = 40,
) -> list[str]:
    """Generar un diff visual lado a lado.

    Args:
        archivo_a: Archivo original.
        archivo_b: Archivo modificado.
        ancho_columna_a: Ancho de la columna del archivo A.
        ancho_columna_b: Ancho de la columna del archivo B.

    Returns:
        Lista de strings con el diff lado a lado.
    """
    with open(archivo_a, "r", encoding="utf-8") as f:
        contenido_a = [linea.rstrip("\n") for linea in f.readlines()]

    with open(archivo_b, "r", encoding="utf-8") as f:
        contenido_b = [linea.rstrip("\n") for linea in f.readlines()]

    dif = difflib.UnifiedDiff(
        fromfile=Path(archivo_a).name,
        tofile=Path(archivo_b).name,
        fromlines=contenido_a,
        tolines=contenido_b,
        lineterm="",
    )

    lineas = []
    ancho_total = max(ancho_columna_a + 40, ancho_columna_b + 40)

    for tag, a_linea, b_linea in dif:
        if tag == "equal":
            linea = f"{' ' * ancho_columna_a}{a_linea:<{ancho_columna_a}}{' ' * 12}{b_linea}"
        elif tag == "delete":
            linea = f"{tag} {a_linea:<{ancho_columna_a}}{' ' * (ancho_total - len(linea))}"
        else:
            linea = f"+ {b_linea:<{ancho_columna_b}}"

        lineas.append(linea)

    return lineas


def resumen_cambios(
    archivo_original: str,
    archivo_modificado: str,
) -> dict[str, any]:
    """Obtener un resumen de los cambios entre dos archivos.

    Args:
        archivo_original: Archivo original.
        archivo_modificado: Archivo modificado.

    Returns:
        Diccionario con estadísticas de cambios.
    """
    with open(archivo_original, "r", encoding="utf-8") as f:
        contenido_a = [linea.rstrip("\n") for linea in f.readlines()]

    with open(archivo_modificado, "r", encoding="utf-8") as f:
        contenido_b = [linea.rstrip("\n") for linea in f.readlines()]

    dif = difflib.SequenceMatcher(None, contenido_a, contenido_b)

    return {
        "archivos": {
            Path(archivo_original).name: len(contenido_a),
            Path(archivo_modificado).name: len(contenido_b),
        },
        "lineas_totales_original": len(contenido_a),
        "lineas_totales_modificadas": len(contenido_b),
        "bloques_identicos_mayores": dif.block_size(),
        "similitud_secuencial": round(100 * dif.ratio(), 2),
    }


if __name__ == "__main__":
    # Demostración
    print("=== GENERADOR DE PATCHES ===\n")

    archivo_original = "skills/ejercicios/checksums.py"
    archivo_modificado = "skills/ejercicios/git_patch_generator.py"

    if Path(archivo_original).exists() and Path(archivo_modificado).exists():
        diff = generar_diff_unificado(archivo_original, archivo_modificado)

        print("=== DIF UNIFICADO ===")
        for linea in diff:
            print(linea)

        print("\n=== RESUMEN DE CAMBIOS ===")
        resumen = resumen_cambios(archivo_original, archivo_modificado)
        for clave, valor in resumen.items():
            if isinstance(valor, dict):
                for subclave, subvalor in valor.items():
                    print(f"  {subclave}: {subvalor}")
            else:
                print(f"  {clave}: {valor}")

    else:
        print("Archivos de demostración no encontrados.")