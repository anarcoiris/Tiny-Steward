#!/usr/bin/env python3
"""Generador de árbol visual de directorios con estadísticas.

Muestra una representación en árbol del sistema de archivos, incluyendo:
- Conteo de archivos y directorios por nivel
- Tamaño total por directorio (recursivo)
- Filtrado por extensión, patrón o tipo
- Opciones de formato (ASCII art, indentación simple)

Ejemplo:
    from file_tree_generator import arbol_directorio

    print(arbol_directorio("C:\\Users\\soyko\\Documents"))
"""


def arbol_directorio(
    ruta_base: str = ".",
    max_profundidad: int | None = None,
    prefijos: list[str] | None = None,
    mostrar_tamano: bool = True,
    formato: str = "ascii"
) -> str:
    """Generar un árbol visual de directorios.

    Args:
        ruta_base: Ruta base del directorio a listar (por defecto ".").
        max_profundidad: Profundidad máxima a mostrar (-1 para infinito).
        prefijos: Lista de prefijos de ruta para filtrar entradas.
        mostrar_tamano: Si True, muestra el tamaño total en cada directorio.
        formato: "ascii" (con ramas |+-) o "simple" (solo indentación).

    Returns:
        String con la representación del árbol.
    """
    import os
    from pathlib import Path

    path_base = Path(ruta_base).resolve()

    if not path_base.exists():
        return f"# Error: El directorio '{ruta_base}' no existe."

    if max_profundidad is None or max_profundidad < 0:
        max_profundidad = float("inf")

    # Construir el árbol recursivamente
    nodos, _ = construir_arbol(path_base, prefijos)

    # Formatear salida
    if formato == "ascii":
        return formateo_ascii(nodos, mostrar_tamano=mostrar_tamano)
    else:
        return formateo_simple(nodos, mostrar_tamano=mostrar_tamano)


def construir_arbol(
    path_actual: Path,
    prefijos: list[str] | None = None,
    profundidad_actual: int = 0
) -> tuple[list[dict], dict]:
    """Construir una estructura de árbol desde un directorio.

    Args:
        path_actual: Ruta del directorio actual.
        prefijos: Filtrar solo estas subcarpetas (opcional).
        profundidad_actual: Profundidad actual en el árbol.

    Returns:
        Tupla con (lista de nodos, estadísticas globales).
    """
    import os

    nodos = []
    estadisticas = {
        "archivos": 0,
        "directorios": 0,
        "tamanio_total_bytes": 0,
    }

    try:
        items = list(os.scandir(path_actual))
    except PermissionError:
        return [], {"archivos": 0, "directorios": 0, "tamanio_total_bytes": 0}

    for item in sorted(items, key=lambda x: (x.is_dir(), not x.name.startswith("."), x.name)):
        nombre = item.name

        # Filtrar por prefijos si aplica
        if prefijos is not None and not any(nombre.startswith(p) for p in prefijos):
            continue

        if item.is_dir(follow_symlinks=False):
            # Es un directorio: recursividad
            sub_nodos, sub_estadisticas = construir_arbol(
                Path(path_actual) / nombre,
                prefijos=prefijos,
                profundidad_actual=profundidad_actual + 1
            )

            nodo = {
                "nombre": nombre,
                "tipo": "dir",
                "es_directorio": True,
                "contenido": sub_nodos,
                "tamanio_bytes": sub_estadisticas["tamanio_total_bytes"],
            }
            nodos.append(nodo)

            # Acumular estadísticas globales (no recursivamente para no duplicar)
            estadisticas["directorios"] += 1
            estadisticas["tamanio_total_bytes"] = sub_estadisticas["tamanio_total_bytes"]

        else:
            # Es un archivo
            try:
                size = item.stat().st_size
            except OSError:
                size = 0

            nodo = {
                "nombre": nombre,
                "tipo": "file",
                "es_directorio": False,
                "contenido": None,
                "tamanio_bytes": size,
            }
            nodos.append(nodo)

            estadisticas["archivos"] += 1
            estadisticas["tamanio_total_bytes"] += size

    return nodos, estadisticas


def formateo_ascii(
    nodos: list[dict],
    mostrar_tamano: bool = True
) -> str:
    """Formatear el árbol en estilo ASCII art.

    Args:
        nodos: Lista de nodos construida por construir_arbol().
        mostrar_tamano: Si se muestra el tamaño en cada directorio.

    Returns:
        String con representación ASCII del árbol.
    """
    lineas = []

    # Cabecera
    lineas.append("╭" + "─" * 78 + "╮")
    lineas.append(f"│  📁 Árbol de directorios — {len(nodos)} entradas │")
    lineas.append("╰" + "─" * 78 + "╯")

    # Título con estadísticas globales
    total_archivos = sum(1 for n in nodos if not n["es_directorio"])
    total_direc = sum(1 for n in nodos if n["es_directorio"])
    total_tamano_bytes = sum(n.get("tamanio_bytes", 0) or 0 for n in nodos)

    lineas.append("")
    lineas.append(f"  Archivos: {total_archivos} | Directorios: {total_direc}")
    if mostrar_tamano and total_tamano_bytes > 0:
        import os
        tamanio_humanizado = _formatar_tamanio(total_tamano_bytes)
        lineas.append(f"  Tamaño total: {tamanio_humanizado}")

    lineas.append("")

    # Renderizar cada nodo con ramas ASCII
    for i, nodo in enumerate(nodos):
        nombre = nodo["nombre"]
        tipo = "📁 DIR" if nodo["es_directorio"] else "📄 FILE"

        if nodo["es_directorio"]:
            contenido = nodo.get("contenido", [])
            linea = f"├── {tipo}  {nombre:<40}"
            if mostrar_tamano and nodo.get("tamanio_bytes") is not None:
                t = _formatar_tamanio(nodo["tamanio_bytes"])
                linea += f"  [{t}]"

            # Añadir sub-nodos con ramas
            for j, sub in enumerate(contenido):
                indentacion = "│   " if j < len(contenido) - 1 else "    "
                nombre_sub = sub["nombre"]
                tipo_sub = "📁 DIR" if sub["es_directorio"] else "📄 FILE"

                linea += f"\n{indentacion}├── {tipo_sub:<5}"

                # Tamaño del sub-nodo
                if mostrar_tamano and sub.get("tamanio_bytes") is not None:
                    t = _formatar_tamanio(sub["tamanio_bytes"])
                    linea += f"  [{t}]"

            lineas.append(linea)
        else:
            linea = f"├── {tipo:<5} {nombre}"
            if mostrar_tamano and nodo.get("tamanio_bytes") is not None:
                t = _formatar_tamanio(nodo["tamanio_bytes"])
                linea += f"  [{t}]"
            lineas.append(linea)

    # Pie
    lineas.append("")
    lineas.append(f"  Total de entradas mostradas: {len(nodos)}")

    return "\n".join(lineas)


def formateo_simple(
    nodos: list[dict],
    mostrar_tamano: bool = True
) -> str:
    """Formatear el árbol con indentación simple (sin arte ASCII).

    Args:
        nodos: Lista de nodos.
        mostrar_tamano: Mostrar tamaño.

    Returns:
        String con representación plana.
    """
    lineas = []
    lineas.append("=== Árbol de directorios (formato simple) ===")
    lineas.append("")

    for nodo in nodos:
        indentacion = "  " * (nodo.get("_profundidad", 0))
        nombre = nodo["nombre"]
        tipo = "[DIR]" if nodo["es_directorio"] else "[FILE]"

        linea = f"{indentacion}{tipo} {nodo['nombre']}"

        if mostrar_tamano and nodo.get("tamanio_bytes") is not None:
            t = _formatar_tamanio(nodo["tamanio_bytes"])
            linea += f"  [{t}]"

        lineas.append(linea)

    return "\n".join(lineas)


def _formatar_tamanio(tamano_bytes: int) -> str:
    """Convertir bytes a una representación humana legible.

    Args:
        tamanio_bytes: Tamaño en bytes.

    Returns:
        String con formato (ej. "2.3 MB").
    """
    if tamanio_bytes < 1024:
        return f"{tamanio_bytes} B"
    elif tamanio_bytes < 1024 ** 2:
        return f"{tamanio_bytes / 1024:.1f} KB"
    elif tamanio_bytes < 1024 ** 3:
        return f"{tamanio_bytes / (1024**2):.1f} MB"
    else:
        return f"{tamanio_bytes / (1024**3):.1f} GB"


if __name__ == "__main__":
    # Demostración
    print(arbol_directorio(".", max_profundidad=3, mostrar_tamano=True))