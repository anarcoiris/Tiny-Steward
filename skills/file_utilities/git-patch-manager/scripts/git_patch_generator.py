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
from typing import Any, Optional


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

    dif = difflib.unified_diff(
        contenido_a,
        contenido_b,
        fromfile=Path(archivo_a).name,
        tofile=Path(archivo_b).name,
        lineterm="",
        n=contexto,
    )

    diff_lines = list(dif)
    if num_líneas is not None and num_líneas > 0:
        diff_lines = diff_lines[:num_líneas]

    return diff_lines


def generar_patch(
    archivo_original: str,
    archivo_modificado: str,
    formato: str = "patch",
    contexto: int = 3,
) -> str:
    """Generar un patch aplicable entre dos archivos.

    Args:
        archivo_original: Archivo original.
        archivo_modificado: Archivo modificado.
        formato: "patch" (unified diff aplicable) o "diff" (comparación cruda Differ).
        contexto: Líneas de contexto para el patch unificado.

    Returns:
        String con el contenido del patch.
    """
    if formato == "patch":
        diff_lines = generar_diff_unificado(archivo_original, archivo_modificado, contexto=contexto)
        return "\n".join(diff_lines)
    else:
        with open(archivo_original, "r", encoding="utf-8", errors="replace") as f:
            contenido_a = [linea.rstrip("\r\n") for linea in f.readlines()]
        with open(archivo_modificado, "r", encoding="utf-8", errors="replace") as f:
            contenido_b = [linea.rstrip("\r\n") for linea in f.readlines()]
        dif = difflib.Differ()
        return "\n".join(dif.compare(contenido_a, contenido_b))


def aplicar_patch(
    archivo_destino: str,
    contenido_patch: str,
    crear_archivo: bool = False,
) -> dict[str, Any]:
    """Aplicar un patch unified a un archivo.

    Args:
        archivo_destino: Archivo donde aplicar el patch.
        contenido_patch: String con el contenido del patch.
        crear_archivo: Si True y el archivo no existe, se crea.

    Returns:
        Diccionario con el resultado de la aplicación.
    """
    import re

    dest_path = Path(archivo_destino)
    if not dest_path.exists():
        if crear_archivo:
            orig_lines: list[str] = []
        else:
            return {"error": f"Archivo no encontrado: {archivo_destino}"}
    else:
        try:
            with open(archivo_destino, "r", encoding="utf-8", errors="replace") as f:
                orig_lines = [line.rstrip("\r\n") for line in f.readlines()]
        except Exception as e:
            return {"error": f"Error leyendo {archivo_destino}: {e}"}

    patch_lines = contenido_patch.splitlines()
    if not patch_lines:
        return {
            "archivos_modificados": [archivo_destino],
            "lineas_agregadas": 0,
            "lineas_eliminadas": 0,
        }

    hunk_regex = re.compile(r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@")
    result_lines = list(orig_lines)
    offset = 0
    added_count = 0
    deleted_count = 0

    i = 0
    while i < len(patch_lines):
        line = patch_lines[i]
        match = hunk_regex.match(line)
        if not match:
            i += 1
            continue

        orig_start = int(match.group(1))
        orig_idx = max(0, orig_start - 1) + offset

        i += 1
        hunk_lines = []
        while i < len(patch_lines) and not patch_lines[i].startswith("@@"):
            hunk_lines.append(patch_lines[i])
            i += 1

        cur_idx = orig_idx
        for hline in hunk_lines:
            if not hline:
                continue
            prefix = hline[0]
            val = hline[1:]
            if prefix == " ":
                cur_idx += 1
            elif prefix == "-":
                if cur_idx < len(result_lines):
                    del result_lines[cur_idx]
                deleted_count += 1
                offset -= 1
            elif prefix == "+":
                result_lines.insert(cur_idx, val)
                cur_idx += 1
                added_count += 1
                offset += 1

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(archivo_destino, "w", encoding="utf-8") as f:
        for l in result_lines:
            f.write(l + "\n")

    return {
        "archivos_modificados": [archivo_destino],
        "lineas_agregadas": added_count,
        "lineas_eliminadas": deleted_count,
    }


def diff_lado_al_lado(
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
    with open(archivo_a, "r", encoding="utf-8", errors="replace") as f:
        contenido_a = [linea.rstrip("\r\n") for linea in f.readlines()]

    with open(archivo_b, "r", encoding="utf-8", errors="replace") as f:
        contenido_b = [linea.rstrip("\r\n") for linea in f.readlines()]

    matcher = difflib.SequenceMatcher(None, contenido_a, contenido_b)
    lineas = []
    w_a = max(20, ancho_columna_a)
    w_b = max(20, ancho_columna_b)

    header = f"{'ARCHIVO A (' + Path(archivo_a).name + ')':<{w_a}} | {'ARCHIVO B (' + Path(archivo_b).name + ')':<{w_b}}"
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


def resumen_cambios(
    archivo_original: str,
    archivo_modificado: str,
) -> dict[str, Any]:
    """Obtener un resumen de los cambios entre dos archivos.

    Args:
        archivo_original: Archivo original.
        archivo_modificado: Archivo modificado.

    Returns:
        Diccionario con estadísticas de cambios.
    """
    with open(archivo_original, "r", encoding="utf-8", errors="replace") as f:
        contenido_a = [linea.rstrip("\r\n") for linea in f.readlines()]

    with open(archivo_modificado, "r", encoding="utf-8", errors="replace") as f:
        contenido_b = [linea.rstrip("\r\n") for linea in f.readlines()]

    matcher = difflib.SequenceMatcher(None, contenido_a, contenido_b)
    match = matcher.find_longest_match(0, len(contenido_a), 0, len(contenido_b))

    return {
        "archivos": {
            Path(archivo_original).name: len(contenido_a),
            Path(archivo_modificado).name: len(contenido_b),
        },
        "lineas_totales_original": len(contenido_a),
        "lineas_totales_modificadas": len(contenido_b),
        "bloques_identicos_mayores": match.size,
        "similitud_secuencial": round(100 * matcher.ratio(), 2),
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