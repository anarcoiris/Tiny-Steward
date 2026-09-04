#!/usr/bin/env python3
"""Detector y conversor de codificaciones de archivos de texto.

Identifica de manera determinista y sin dependencias externas la codificación
de un archivo (BOMs, UTF-8, UTF-16 LE/BE, ASCII, Windows-1252, ISO-8859-1) y
permite transcodificar entre distintos esquemas.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

BOM_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
]


def es_archivo_binario(ruta_archivo: str, max_bytes: int = 8192) -> bool:
    """Verifica si un archivo parece contener datos binarios (no texto).

    Args:
        ruta_archivo: Ruta al archivo.
        max_bytes: Cantidad máxima de bytes a muestrear.

    Returns:
        True si contiene bytes nulos o alta densidad de caracteres de control.
    """
    p = Path(ruta_archivo)
    if not p.is_file():
        return False

    try:
        with open(p, "rb") as f:
            chunk = f.read(max_bytes)
        if not chunk:
            return False
        # El byte nulo es característico de formatos binarios o UTF-16 sin BOM
        if b"\x00" in chunk and not (chunk.startswith(b"\xff\xfe") or chunk.startswith(b"\xfe\xff")):
            # Si más del 20% son nulos intercalados, podría ser UTF-16, pero si hay bytes
            # no imprimibles es considerado binario
            control_chars = sum(1 for b in chunk if b < 32 and b not in (9, 10, 13))
            if control_chars > len(chunk) * 0.1:
                return True
        return False
    except Exception:
        return False


def detectar_codificacion(ruta_archivo: str, byte_samples: int = 65536) -> dict[str, Any]:
    """Detecta la codificación de caracteres de un archivo de texto.

    Args:
        ruta_archivo: Ruta al archivo.
        byte_samples: Muestra en bytes para análisis heurístico.

    Returns:
        Diccionario con encoding detectado, flags de BOM y ASCII, y nivel de confianza.
    """
    p = Path(ruta_archivo)
    if not p.is_file():
        return {"error": f"Archivo no encontrado: {ruta_archivo}"}

    try:
        tamanio = p.stat().st_size
        with open(p, "rb") as f:
            muestra = f.read(byte_samples)

        if not muestra:
            return {
                "encoding": "ascii",
                "has_bom": False,
                "is_ascii": True,
                "confidence": 1.0,
                "tamanio_bytes": tamanio,
            }

        # 1. Chequeo de firmas BOM
        for bom, enc in BOM_SIGNATURES:
            if muestra.startswith(bom):
                return {
                    "encoding": enc,
                    "has_bom": True,
                    "is_ascii": False,
                    "confidence": 1.0,
                    "tamanio_bytes": tamanio,
                }

        # 2. Comprobación de ASCII puro
        try:
            muestra.decode("ascii")
            return {
                "encoding": "ascii",
                "has_bom": False,
                "is_ascii": True,
                "confidence": 1.0,
                "tamanio_bytes": tamanio,
            }
        except UnicodeDecodeError:
            pass

        # 3. Comprobación de UTF-8 estricto
        try:
            muestra.decode("utf-8")
            return {
                "encoding": "utf-8",
                "has_bom": False,
                "is_ascii": False,
                "confidence": 0.99,
                "tamanio_bytes": tamanio,
            }
        except UnicodeDecodeError:
            pass

        # 4. Comprobación de UTF-16 sin BOM (intercalación de nulos)
        if len(muestra) >= 4:
            if muestra[1::2].count(0) > len(muestra[1::2]) * 0.8:
                try:
                    muestra.decode("utf-16-le")
                    return {
                        "encoding": "utf-16-le",
                        "has_bom": False,
                        "is_ascii": False,
                        "confidence": 0.90,
                        "tamanio_bytes": tamanio,
                    }
                except UnicodeDecodeError:
                    pass

            if muestra[0::2].count(0) > len(muestra[0::2]) * 0.8:
                try:
                    muestra.decode("utf-16-be")
                    return {
                        "encoding": "utf-16-be",
                        "has_bom": False,
                        "is_ascii": False,
                        "confidence": 0.90,
                        "tamanio_bytes": tamanio,
                    }
                except UnicodeDecodeError:
                    pass

        # 5. Fallback a Windows-1252 / CP1252 y Latin-1 (ISO-8859-1)
        try:
            muestra.decode("cp1252")
            return {
                "encoding": "windows-1252",
                "has_bom": False,
                "is_ascii": False,
                "confidence": 0.75,
                "tamanio_bytes": tamanio,
            }
        except UnicodeDecodeError:
            pass

        return {
            "encoding": "latin-1",
            "has_bom": False,
            "is_ascii": False,
            "confidence": 0.50,
            "tamanio_bytes": tamanio,
        }
    except Exception as e:
        return {"error": f"Error al analizar codificación: {e}"}


def convertir_codificacion(
    ruta_origen: str,
    ruta_destino: str,
    codificacion_destino: str = "utf-8",
    codificacion_origen: str | None = None,
    sobreescribir: bool = False,
) -> dict[str, Any]:
    """Transcodifica un archivo de texto de una codificación a otra.

    Args:
        ruta_origen: Archivo a leer.
        ruta_destino: Archivo resultante.
        codificacion_destino: Encoding destino (por defecto 'utf-8').
        codificacion_origen: Encoding origen explícito (o auto-detectado si None).
        sobreescribir: Permite sobreescribir el destino si existe.

    Returns:
        Diccionario con resumen de la conversión y caracteres procesados.
    """
    src = Path(ruta_origen)
    if not src.is_file():
        return {"error": f"El archivo de origen no existe: {ruta_origen}"}

    dst = Path(ruta_destino)
    if dst.exists() and not sobreescribir:
        return {"error": f"El archivo destino ya existe y sobreescribir=False: {ruta_destino}"}

    enc_src = codificacion_origen
    if not enc_src:
        det = detectar_codificacion(str(src))
        if "error" in det:
            return det
        enc_src = det.get("encoding", "utf-8")

    try:
        with open(src, "r", encoding=enc_src, errors="replace") as f_in:
            contenido = f_in.read()

        dst.parent.mkdir(parents=True, exist_ok=True)
        with open(dst, "w", encoding=codificacion_destino, errors="replace") as f_out:
            f_out.write(contenido)

        return {
            "estado": "convertido",
            "origen": str(src),
            "destino": str(dst),
            "encoding_origen": enc_src,
            "encoding_destino": codificacion_destino,
            "caracteres_escritos": len(contenido),
            "bytes_finales": dst.stat().st_size,
        }
    except Exception as e:
        return {"error": f"Fallo al convertir codificación: {e}"}
