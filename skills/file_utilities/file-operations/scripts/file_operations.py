#!/usr/bin/env python3
"""Operaciones atómicas y seguras sobre archivos del sistema.

Provee funciones de utilidad para manipulación de archivos con garantías
de integridad, backups automáticos y transacciones atómicas.

Operaciones disponibles:
- copiar_archivo
- mover_archivo
- renombrar_archivo
- truncar_archivo
- anteponer_lineas (prepend)
- anexar_lineas (append)
- eliminar_archivo_seguro (con backup de reversión)
- restaurar_backup
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any


def copiar_archivo(
    origen: str,
    destino: str,
    sobreescribir: bool = False,
    crear_directorios: bool = True,
) -> dict[str, Any]:
    """Copia un archivo de origen a destino con validaciones previas.

    Args:
        origen: Ruta del archivo fuente.
        destino: Ruta del archivo destino o directorio.
        sobreescribir: Si es False y el destino existe, aborta con error.
        crear_directorios: Si True, crea los directorios padres si no existen.

    Returns:
        Diccionario con estado, rutas y bytes copiados.
    """
    src = Path(origen)
    if not src.is_file():
        return {"error": f"El archivo de origen no existe o no es regular: {origen}"}

    dst = Path(destino)
    if dst.is_dir():
        dst = dst / src.name

    if dst.exists() and not sobreescribir:
        return {"error": f"El archivo destino ya existe y sobreescribir=False: {dst}"}

    if crear_directorios:
        dst.parent.mkdir(parents=True, exist_ok=True)

    try:
        shutil.copy2(src, dst)
        size = dst.stat().st_size
        return {
            "estado": "copiado",
            "origen": str(src),
            "destino": str(dst),
            "bytes": size,
        }
    except Exception as e:
        return {"error": f"Fallo al copiar archivo: {e}"}


def mover_archivo(
    origen: str,
    destino: str,
    sobreescribir: bool = False,
) -> dict[str, Any]:
    """Mueve o traslada un archivo de origen a destino.

    Args:
        origen: Archivo a mover.
        destino: Ruta destino.
        sobreescribir: Permite reemplazar el archivo de destino si ya existe.

    Returns:
        Diccionario con el resultado de la operación.
    """
    src = Path(origen)
    if not src.exists():
        return {"error": f"El archivo de origen no existe: {origen}"}

    dst = Path(destino)
    if dst.is_dir():
        dst = dst / src.name

    if dst.exists() and not sobreescribir:
        return {"error": f"El archivo destino ya existe: {dst}"}

    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(src, dst)
        return {
            "estado": "movido",
            "origen": str(src),
            "destino": str(dst),
        }
    except Exception as e:
        return {"error": f"Fallo al mover archivo: {e}"}


def renombrar_archivo(ruta: str, nuevo_nombre: str) -> dict[str, Any]:
    """Renombra un archivo dentro de su mismo directorio contenedor.

    Args:
        ruta: Ruta completa al archivo.
        nuevo_nombre: Solo el nombre de archivo final (sin paths).

    Returns:
        Diccionario con estado y nueva ruta completa.
    """
    p = Path(ruta)
    if not p.exists():
        return {"error": f"El archivo no existe: {ruta}"}

    nuevo_p = p.parent / Path(nuevo_nombre).name
    if nuevo_p.exists() and nuevo_p != p:
        return {"error": f"Ya existe un archivo con el nuevo nombre: {nuevo_p}"}

    try:
        p.rename(nuevo_p)
        return {
            "estado": "renombrado",
            "ruta_anterior": str(p),
            "ruta_nueva": str(nuevo_p),
        }
    except Exception as e:
        return {"error": f"Fallo al renombrar archivo: {e}"}


def truncar_archivo(ruta: str, tamanio_bytes: int = 0) -> dict[str, Any]:
    """Trunca o recorta un archivo al tamaño en bytes especificado.

    Args:
        ruta: Archivo a truncar.
        tamanio_bytes: Tamaño final en bytes (por defecto 0, vacía el archivo).

    Returns:
        Diccionario con el tamaño resultante.
    """
    p = Path(ruta)
    if not p.exists():
        return {"error": f"El archivo no existe: {ruta}"}

    try:
        with open(p, "r+b") as f:
            f.truncate(max(0, int(tamanio_bytes)))
        return {
            "estado": "truncado",
            "ruta": str(p),
            "bytes_finales": p.stat().st_size,
        }
    except Exception as e:
        return {"error": f"Fallo al truncar archivo: {e}"}


def anteponer_lineas(
    ruta: str,
    lineas: list[str] | str,
    crear_si_no_existe: bool = True,
    encoding: str = "utf-8",
) -> dict[str, Any]:
    """Antepone líneas de texto al inicio de un archivo (prepend atómico).

    Escribe de forma atómica usando un archivo temporal para prevenir corrupción.

    Args:
        ruta: Ruta al archivo.
        lineas: Cadena de texto o lista de líneas a anteponer.
        crear_si_no_existe: Crea el archivo si aún no existe.
        encoding: Codificación de texto (utf-8 por defecto).

    Returns:
        Diccionario con líneas insertadas y total de líneas resultantes.
    """
    p = Path(ruta)
    if isinstance(lineas, str):
        nuevas = lineas.splitlines(keepends=True)
    else:
        nuevas = [l if l.endswith("\n") else l + "\n" for l in lineas]

    contenido_previo: list[str] = []
    if p.exists():
        try:
            with open(p, "r", encoding=encoding, errors="replace") as f:
                contenido_previo = f.readlines()
        except Exception as e:
            return {"error": f"Error leyendo contenido previo: {e}"}
    elif not crear_si_no_existe:
        return {"error": f"El archivo no existe y crear_si_no_existe=False: {ruta}"}

    p.parent.mkdir(parents=True, exist_ok=True)
    temp_fd, temp_path = tempfile.mkstemp(dir=p.parent, prefix="prepend_")
    try:
        with os.fdopen(temp_fd, "w", encoding=encoding) as f:
            for n in nuevas:
                f.write(n if n.endswith(("\n", "\r\n")) else n + "\n")
            for ant in contenido_previo:
                f.write(ant)
        shutil.move(temp_path, p)
        return {
            "estado": "antepuesto",
            "ruta": str(p),
            "lineas_agregadas": len(nuevas),
            "total_lineas": len(nuevas) + len(contenido_previo),
        }
    except Exception as e:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        return {"error": f"Fallo en anteponer líneas: {e}"}


def anexar_lineas(
    ruta: str,
    lineas: list[str] | str,
    crear_si_no_existe: bool = True,
    encoding: str = "utf-8",
) -> dict[str, Any]:
    """Anexa líneas de texto al final de un archivo (append seguro).

    Args:
        ruta: Ruta al archivo.
        lineas: Cadena de texto o lista de líneas a anexar.
        crear_si_no_existe: Crea el archivo si no existe.
        encoding: Codificación de texto.

    Returns:
        Diccionario con estado y líneas anexadas.
    """
    p = Path(ruta)
    if isinstance(lineas, str):
        nuevas = lineas.splitlines(keepends=True)
    else:
        nuevas = [l if l.endswith("\n") else l + "\n" for l in lineas]

    if not p.exists() and not crear_si_no_existe:
        return {"error": f"El archivo no existe y crear_si_no_existe=False: {ruta}"}

    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(p, "a", encoding=encoding) as f:
            for l in nuevas:
                f.write(l if l.endswith(("\n", "\r\n")) else l + "\n")
        return {
            "estado": "anexado",
            "ruta": str(p),
            "lineas_agregadas": len(nuevas),
        }
    except Exception as e:
        return {"error": f"Fallo al anexar líneas: {e}"}


def eliminar_archivo_seguro(ruta: str, con_backup: bool = True) -> dict[str, Any]:
    """Elimina un archivo, guardando opcionalmente una copia de reversión (.bak).

    Args:
        ruta: Archivo a eliminar.
        con_backup: Si es True, crea una copia en .bak antes de borrar el original.

    Returns:
        Diccionario con el estado y la ruta del backup si aplica.
    """
    p = Path(ruta)
    if not p.is_file():
        return {"error": f"El archivo no existe o no es regular: {ruta}"}

    backup_path = None
    try:
        if con_backup:
            backup_path = p.with_suffix(p.suffix + ".bak")
            shutil.copy2(p, backup_path)
        p.unlink()
        return {
            "estado": "eliminado",
            "ruta_eliminada": str(p),
            "backup_disponible": str(backup_path) if backup_path else None,
        }
    except Exception as e:
        return {"error": f"Fallo al eliminar archivo: {e}"}


def restaurar_backup(ruta_backup: str, ruta_original: str) -> dict[str, Any]:
    """Restaura un archivo desde su copia de respaldo (.bak).

    Args:
        ruta_backup: Ruta al fichero .bak.
        ruta_original: Ruta del archivo que se desea restaurar.

    Returns:
        Diccionario con el resultado de la restauración.
    """
    bak = Path(ruta_backup)
    if not bak.is_file():
        return {"error": f"El archivo de backup no existe: {ruta_backup}"}

    orig = Path(ruta_original)
    orig.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(bak, orig)
        return {
            "estado": "restaurado",
            "backup": str(bak),
            "destino": str(orig),
        }
    except Exception as e:
        return {"error": f"Fallo al restaurar backup: {e}"}
