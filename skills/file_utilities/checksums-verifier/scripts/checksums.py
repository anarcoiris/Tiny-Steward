#!/usr/bin/env python3
"""Herramienta para calcular checksums de archivos.

Permite verificar la integridad de archivos mediante MD5, SHA1, SHA256,
SHA384 y SHA512. Útil para:
- Verificar descargas
- Detectar corrupción de datos
- Firmas digitales básicas
- Comparación de versiones sin leer contenido

Ejemplo:
    from checksums import calcular_checksum

    hash_md5 = calcular_checksum("archivo.txt", algoritmo="md5")
    print(hash_md5)
"""


import hashlib
import os
from pathlib import Path
from typing import Optional


def calcular_checksum(
    ruta: str,
    algoritmo: str = "sha256",
    tamanio_bloque: int | None = None,
    binario: bool = True,
) -> str:
    """Calcular el checksum de un archivo.

    Args:
        ruta: Ruta al archivo a verificar.
        algoritmo: Algoritmo hash (md5, sha1, sha256, sha384, sha512).
        tamanio_bloque: Tamaño del bloque para leer (por defecto 8KB para rapidez).
        binario: Si False, tratar el archivo como texto (decodificar UTF-8).

    Returns:
        El hash hexadecimal en minúsculas.

    Raises:
        FileNotFoundError: Si el archivo no existe.
        ValueError: Si el algoritmo no es válido.
    """
    if algoritmo.lower() not in ("md5", "sha1", "sha256", "sha384", "sha512"):
        raise ValueError(
            f"Algoritmo no soportado: {algoritmo}. "
            f"Soportados: md5, sha1, sha256, sha384, sha512."
        )

    hash_obj = hashlib.new(algoritmo.lower())

    with open(ruta, "rb" if binario else "r", encoding="utf-8") as f:
        while True:
            data = f.read(tamanio_bloque or 8 * 1024)
            if not data:
                break
            hash_obj.update(data)

    return hash_obj.hexdigest()


def verificar_checksum(
    ruta_archivo: str,
    checksum_esperado: str,
    algoritmo: str = "sha256",
) -> bool:
    """Verificar si un archivo coincide con su checksum esperado.

    Args:
        ruta_archivo: Ruta al archivo a verificar.
        checksum_esperado: Hash hexadecimal esperado.
        algoritmo: Algoritmo usado para calcular el hash (debe coincidir).

    Returns:
        True si el archivo es válido, False si no coincide o hay error.
    """
    try:
        return calcular_checksum(ruta_archivo, algoritmo) == checksum_esperado.lower()
    except FileNotFoundError:
        print(f"Error: El archivo '{ruta_archivo}' no existe.")
        return False


def generar_manifest(
    directorio: str = ".",
    algoritmo: str = "sha256",
    binario: bool = True,
) -> dict[str, dict]:
    """Generar un manifest (JSON) con checksums de todos los archivos en un directorio.

    Args:
        directorio: Directorio a escanear (por defecto el actual).
        algoritmo: Algoritmo hash para usar.
        binario: Tratar como archivo binario.

    Returns:
        Diccionario con la ruta relativa y su hash para cada archivo.
    """
    manifest = {}

    for raiz, _, archivos in os.walk(directorio):
        for nombre_archivo in archivos:
            if nombre_archivo.startswith("."):
                continue  # saltar archivos ocultos

            ruta_absoluta = os.path.join(raiz, nombre_archivo)

            try:
                checksum = calcular_checksum(ruta_absoluta, algoritmo, binario=binario)
                ruta_relativa = os.path.relpath(ruta_absoluta, directorio)
                manifest[ruta_relativa] = {
                    "algoritmo": algoritmo.upper(),
                    "hash": checksum,
                }

            except (FileNotFoundError, PermissionError):
                pass  # saltar archivos que no se pueden leer

    return manifest


def guardar_manifest(
    directorio: str = ".",
    algoritmo: str = "sha256",
    ruta_manifest: Optional[str] = None,
) -> str:
    """Generar y guardar un manifest JSON con checksums.

    Args:
        directorio: Directorio a escanear.
        algoritmo: Algoritmo hash.
        ruta_manifest: Ruta donde guardar el JSON del manifest.

    Returns:
        Ruta al archivo guardado.
    """
    import json
    from datetime import datetime

    manifest = generar_manifest(directorio, algoritmo)

    if ruta_manifest is None:
        ruta_manifest = os.path.join(directorio, "checksums.json")

    timestamp = datetime.now().isoformat()
    metadata = {
        "generado": timestamp,
        "algoritmo": algoritmo.upper(),
        "archivos_totales": len(manifest),
    }

    with open(ruta_manifest, "w", encoding="utf-8") as f:
        json.dump({**metadata, **manifest}, f, indent=2)

    return ruta_manifest


def cargar_y_verificar_manifest(
    ruta_manifest: str = "checksums.json",
    directorio_actual: Optional[str] = None,
) -> dict:
    """Cargar un manifest y verificar los archivos.

    Args:
        ruta_manifest: Ruta al archivo JSON del manifest.
        directorio_actual: Directorio donde buscar los archivos (por defecto el actual).

    Returns:
        Diccionario con estado de cada verificación:
            - "ok": archivo existe y coincide
            - "modificado": hash no coincide
            - "faltante": archivo esperado no existe
            - "error": hubo un error leyendo el archivo
    """
    import json

    with open(ruta_manifest, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    directorio = directorio_actual or "."

    resultados = {}

    for ruta_relativa, datos in manifest["archivos"].items():
        hash_esperado = datos["hash"]
        ruta_archivo = os.path.join(directorio, ruta_relativa)

        try:
            hash_real = calcular_checksum(ruta_archivo, algoritmo=datos["algoritmo"], binario=True)
            if hash_real == hash_esperado.lower():
                resultados[ruta_relativa] = {"estado": "ok", "hash_actual": hash_real}
            else:
                resultados[ruta_relativa] = {
                    "estado": "modificado",
                    "hash_esperado": hash_esperado,
                    "hash_actual": hash_real,
                }

        except FileNotFoundError:
            resultados[ruta_relativa] = {"estado": "faltante"}
        except (PermissionError, OSError) as e:
            resultados[ruta_relativa] = {"estado": "error", "mensaje": str(e)}

    return resultados


def comparar_checksums(
    ruta_archivo_a: str,
    ruta_archivo_b: str,
    algoritmo: str = "sha256",
) -> dict[str, any]:
    """Comparar dos archivos mediante sus checksums.

    Args:
        ruta_archivo_a: Primer archivo.
        ruta_archivo_b: Segundo archivo.
        algoritmo: Algoritmo hash a usar.

    Returns:
        Diccionario con los hashes de ambos y si coinciden.
    """
    try:
        hash_a = calcular_checksum(ruta_archivo_a, algoritmo)
    except FileNotFoundError:
        return {"error": f"Archivo A no encontrado: {ruta_archivo_a}"}

    try:
        hash_b = calcular_checksum(ruta_archivo_b, algoritmo)
    except FileNotFoundError:
        return {"error": f"Archivo B no encontrado: {ruta_archivo_b}"}

    return {
        "archivo_a": ruta_archivo_a,
        "hash_a": hash_a,
        "archivo_b": ruta_archivo_b,
        "hash_b": hash_b,
        "coinciden": hash_a == hash_b.lower(),
    }


if __name__ == "__main__":
    # Demostración
    import os

    print("=== CHECKSUMS ===\n")

    archivo = __file__  # este propio script

    print(f"MD5:     {calcular_checksum(archivo, 'md5')}")
    print(f"SHA1:    {calcular_checksum(archivo, 'sha1')}")
    print(f"SHA256:  {calcular_checksum(archivo, 'sha256')}")
    print(f"SHA384:  {calcular_checksum(archivo, 'sha384')[:64]}...")
    print(f"SHA512:  {calcular_checksum(archivo, 'sha512')[:64]}...")

    print("\n=== VERIFICACIÓN ===")
    resultado = verificar_checksum(archivo, calcular_checksum(archivo, "sha256"))
    print(f"¿Coincide con SHA256? {resultado}")