#!/usr/bin/env python3
"""Configurador y parser de archivos de configuración.

Soporta múltiples formatos: JSON, YAML (con PyYAML), INI, TOML.
Incluye validación de esquemas, merge inteligente entre configs,
y export/import de configuraciones.

Ejemplo:
    from config_loader import ConfigLoader

    loader = ConfigLoader("config.json")
    loader.cargar()
    print(loader["clave"])
    loader.guardar({"clave": "nuevo valor"})
"""


import json
from pathlib import Path
from typing import Any, Optional


def cargar_json(ruta: str) -> dict[str, Any]:
    """Cargar un archivo JSON.

    Args:
        ruta: Ruta al archivo JSON.

    Returns:
        Diccionario con el contenido del archivo.

    Raises:
        json.JSONDecodeError: Si el contenido no es JSON válido.
    """
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def guardar_json(
    ruta: str,
    datos: dict[str, Any],
    indent: int = 2,
    sort_keys: bool = True
) -> None:
    """Guardar un diccionario como archivo JSON.

    Args:
        ruta: Ruta donde guardar el archivo.
        datos: Diccionario a guardar.
        indent: Indentación (0 para minificado).
        sort_keys: Ordenar las claves alguardar.
    """
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=indent if indent else None)


def cargar_ini(ruta: str) -> dict[str, dict[str, str]]:
    """Cargar un archivo INI (formato de configuración de Python).

    Args:
        ruta: Ruta al archivo INI.

    Returns:
        Diccionario anidado {seccion: {clave: valor}}.
    """
    import configparser

    config = configparser.ConfigParser()
    config.read(ruta, encoding="utf-8")

    resultado = {}
    for seccion in config.sections():
        if seccion == "DEFAULT":
            continue
        resultado[seccion] = dict(config.items(seccion))

    return resultado


def guardar_ini(
    ruta: str,
    datos: dict[str, dict[str, str]],
    seccion_default: Optional[str] = None
) -> None:
    """Guardar un diccionario como archivo INI.

    Args:
        ruta: Ruta del archivo a crear/reescribir.
        datos: Diccionario anidado {seccion: {clave: valor}}.
        seccion_default: Sección por defecto (opcional).
    """
    import configparser

    config = configparser.ConfigParser()

    if seccion_default and seccion_default in datos:
        for clave, valor in datos[seccion_default].items():
            config.set(seccion_default, clave, str(valor))

    for seccion, items in datos.items():
        if seccion != "DEFAULT":
            config[section] = {}
            for clave, valor in items.items():
                config.set(seccion, clave, str(valor))

    with open(ruta, "w", encoding="utf-8") as f:
        config.write(f)


def cargar_yaml(ruta: str) -> dict[str, Any]:
    """Cargar un archivo YAML.

    Args:
        ruta: Ruta al archivo YAML.

    Returns:
        Diccionario con el contenido del archivo.

    Raises:
        ImportError: Si PyYAML no está instalado.
    """
    try:
        import yaml
    except ImportError:
        raise ImportError(
            "PyYAML no está instalado. Instálalo con: pip install pyyaml"
        )

    with open(ruta, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def guardar_yaml(
    ruta: str,
    datos: dict[str, Any],
    default_flow_style: bool = False
) -> None:
    """Guardar un diccionario como archivo YAML.

    Args:
        ruta: Ruta del archivo a crear/reescribir.
        datos: Diccionario a guardar.
        default_flow_style: Si True, usar estilo de flujo por defecto.
    """
    try:
        import yaml
    except ImportError:
        raise ImportError("PyYAML no está instalado.")

    with open(ruta, "w", encoding="utf-8") as f:
        yaml.dump(
            datos,
            f,
            default_flow_style=default_flow_style,
            allow_unicode=True,
            sort_keys=False,
        )


def cargar_toml(ruta: str) -> dict[str, Any]:
    """Cargar un archivo TOML.

    Args:
        ruta: Ruta al archivo TOML.

    Returns:
        Diccionario con el contenido del archivo.

    Raises:
        ImportError: Si tomli no está instalado.
    """
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        try:
            import toml as tomllib
        except ImportError:
            raise ImportError(
                "tomli/toml no está instalado. Instálalo con: pip install tomli"
            )

    with open(ruta, "rb") as f:
        return tomllib.load(f)


def guardar_toml(
    ruta: str,
    datos: dict[str, Any],
) -> None:
    """Guardar un diccionario como archivo TOML.

    Args:
        ruta: Ruta del archivo a crear/reescribir.
        datos: Diccionario a guardar.
    """
    try:
        import tomli_w as tomlw
    except ImportError:
        raise ImportError("tomli-w no está instalado.")

    with open(ruta, "wb") as f:
        f.write(tomlw.dumps(datos).encode("utf-8"))


class ConfigLoader:
    """Clase principal para cargar, validar y guardar configuraciones.

    Soporta múltiples formatos (JSON, YAML, INI) y permite:
        - Cargar desde archivo o texto en memoria
        - Validar contra un esquema (diccionario con tipos esperados)
        - Merge inteligente entre dos configuraciones
        - Exportar/importar configuraciones completas
    """

    def __init__(self, ruta: Optional[str] = None, contenido: Optional[dict | str] = None):
        """Inicializar el cargador.

        Args:
            ruta: Ruta al archivo de configuración.
            contenido: Diccionario o string JSON/YAML para cargar en memoria.
        """
        self._datos: dict[str, Any] = {}
        self._ruta: Optional[str] = None
        self._formato: str | None = None

        if ruta is not None and contenido is not None:
            raise ValueError("No se pueden especificar ambos 'ruta' y 'contenido'.")

        if ruta is not None:
            self.cargar(ruta=ruta)
        elif contenido is not None:
            if isinstance(contenido, str):
                try:
                    self._datos = json.loads(contenido)
                except json.JSONDecodeError:
                    pass  # Intentar YAML después

                if not self._datos and isinstance(contenido, str):
                    try:
                        import yaml
                        self._datos = yaml.safe_load(contenido) or {}
                    except ImportError:
                        pass

            elif isinstance(contenido, dict):
                self._datos = contenido.copy()

    def cargar(self, ruta: str, formato: Optional[str] = None) -> "ConfigLoader":
        """Cargar configuración desde un archivo.

        Args:
            ruta: Ruta al archivo de configuración.
            formato: Formato explícito (json, yaml, ini). Si None, se detecta automáticamente.

        Returns:
            self para permitir chaining.
        """
        path = Path(ruta)

        if not path.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {ruta}")

        # Detectar formato por extensión
        ext = path.suffix.lower()

        if ext == ".json":
            self._formato = "json"
            self._datos = cargar_json(ruta)
        elif ext in (".yaml", ".yml"):
            try:
                import yaml
                self._formato = "yaml"
                self._datos = cargar_yaml(ruta)
            except ImportError:
                raise RuntimeError("PyYAML no está disponible.")
        elif ext == ".ini":
            self._formato = "ini"
            self._datos = cargar_ini(ruta)
        elif ext == ".toml":
            try:
                import tomllib  # Python 3.11+
                with open(ruta, "rb") as f:
                    self._datos = tomllib.load(f)
                self._formato = "toml"
            except (ImportError, ModuleNotFoundError):
                raise RuntimeError("tomli/tomllib no está disponible.")

        else:
            # Intentar detectar automáticamente
            try:
                with open(ruta, "r", encoding="utf-8") as f:
                    contenido = f.read()

                if contenido.strip().startswith("{"):
                    self._formato = "json"
                    self._datos = json.loads(contenido)
                else:
                    import yaml
                    self._formato = "yaml"
                    self._datos = yaml.safe_load(contenido) or {}
            except (json.JSONDecodeError, yaml.YAMLError):
                raise ValueError(f"No se pudo detectar el formato de {ruta}")

        self._ruta = ruta
        return self

    def guardar(self, ruta: Optional[str] = None, formato: Optional[str] = None) -> "ConfigLoader":
        """Guardar la configuración actual a un archivo.

        Args:
            ruta: Ruta donde guardar (si None, usa la ruta original).
            formato: Formato explícito (json, yaml, ini). Si None, se detecta por extensión.

        Returns:
            self para permitir chaining.
        """
        if ruta is None:
            ruta = self._ruta

        if not ruta:
            raise ValueError("No hay una ruta de configuración establecida.")

        ext = Path(ruta).suffix.lower() or ".json"  # default a JSON

        if formato is not None and formato != "ini":
            ext = f".{formato}"

        with open(ruta, "w", encoding="utf-8") as f:
            if ext == ".json":
                guardar_json(ruta, self._datos)
            elif ext in (".yaml", ".yml"):
                guardar_yaml(ruta, self._datos)
            elif ext == ".ini":
                guardar_ini(ruta, {path.stem: self._datos})
            else:
                guardar_json(ruta, self._datos)

        self._ruta = ruta
        return self

    def obtener(self, clave: str, default: Any = None, path: Optional[list[str]] = None) -> Any:
        """Obtener un valor por su clave (soporta puntos para nested keys).

        Args:
            clave: Clave simple o con puntos (ej. "database.host").
            default: Valor a devolver si la clave no existe.
            path: Lista de claves para acceder anidado directamente.

        Returns:
            El valor encontrado o el default.
        """
        if path is not None:
            resultado = self._datos
            for key in path:
                if isinstance(resultado, dict) and key in resultado:
                    resultado = resultado[key]
                else:
                    return default

            return resultado

        partes = clave.split(".")
        resultado = self._datos

        for parte in partes:
            if isinstance(resultado, dict) and parte in resultado:
                resultado = resultado[parte]
            else:
                return default

        return resultado

    def __getitem__(self, clave: str) -> Any:
        """Acceder a un valor con sintaxis de diccionario."""
        return self.obtener(clave)

    def __setitem__(self, clave: str, valor: Any) -> None:
        """Asignar un valor (soporta claves anidadas con puntos)."""
        partes = clave.split(".")[:-1]  # todas menos la última
        ultima_clave = clave.rsplit(".", 1)[-1]

        if not partes:
            self._datos[ultima_clave] = valor
        else:
            dict_actualizar_nido(self._datos, partes, ultima_clave)
            self._datos[partes[-1]][ultima_clave] = valor

    def __contains__(self, clave: str) -> bool:
        """Verificar si una clave existe."""
        return self.obtener(clave, default=None) is not None

    def merge(self, otra_config: "ConfigLoader") -> "ConfigLoader":
        """Merge inteligente con otra configuración.

        Reglas de merge:
            - Claves anidadas se fusionan recursivamente
            - Listas se concatenan (no sobrescriben)
            - Dicts se fusionan recursivamente
            - Escalares sobrescriben el valor existente

        Args:
            otra_config: Otra instancia de ConfigLoader.

        Returns:
            Una nueva ConfigLoader con los datos mergeados.
        """
        if not isinstance(otra_config, ConfigLoader):
            raise TypeError("Se espera una ConfigLoader.")

        # Merge recursivo
        resultado = dict(self._datos)

        def _merge(a: Any, b: Any) -> Any:
            if isinstance(a, dict) and isinstance(b, dict):
                return {**a, **_merge_dicto(b)}  # merge recursivo
            elif isinstance(a, list) and isinstance(b, list):
                return a + b  # concatenar listas
            else:
                return b  # sobrescribir escalares

        def _merge_dicto(d: dict) -> dict:
            for key in d:
                if key in resultado:
                    resultado[key] = _merge(resultado[key], d[key])
                else:
                    resultado[key] = d[key]
            return resultado

        resultado = _merge_dicto(otra_config._datos)
        self._datos = resultado
        return self

    def validar(self, esquema: dict[str, Any]) -> list[str]:
        """Validar la configuración contra un esquema.

        El esquema define tipos esperados para ciertas claves.

        Ejemplo de esquema:
            {
                "host": {"tipo": str},
                "puerto": {"tipo": int, "minimo": 1, "maximo": 65535},
                "usuarios": {"tipo": list, "elemento_tipo": dict},
            }

        Args:
            esquema: Diccionario con reglas de validación.

        Returns:
            Lista de mensajes de error (vacía si es válida).
        """
        errores = []

        for clave, regla in esquema.items():
            valor = self.obtener(clave, default=None)

            if valor is None and "requerido" in regla and regla["requerido"]:
                errores.append(f"Falta la clave '{clave}' (es requerida).")
                continue

            if valor is not None:
                tipo_esperado = regla.get("tipo", object)
                minimo = regla.get("minimo")
                maximo = regla.get("maximo")

                # Validar tipo
                try:
                    if tipo_esperado == str and not isinstance(valor, str):
                        errores.append(
                            f"'{clave}': se espera un string, got {type(valor).__name__}."
                        )
                    elif tipo_esperado == int and not isinstance(valor, (int, float)):
                        errores.append(
                            f"'{clave}': se espera un número entero, got {type(valor).__name__}."
                        )
                    elif tipo_esperado == list and not isinstance(valor, list):
                        errores.append(
                            f"'{clave}': se espera una lista, got {type(valor).__name__}."
                        )

                except (TypeError, ValueError):
                    errores.append(f"'{clave}': no se pudo validar el tipo.")

                # Validar rangos numéricos
                if minimo is not None and valor < minimo:
                    errores.append(
                        f"'{clave}': valor {valor} es menor que el mínimo {minimo}."
                    )
                if maximo is not None and valor > maximo:
                    errores.append(
                        f"'{clave}': valor {valor} es mayor que el máximo {maximo}."
                    )

        return errores


# Función auxiliar para actualizar diccionarios anidados
def dicto_actualizar_nido(d: dict, partes: list[str], clave_final: str) -> None:
    """Actualizar un valor en un diccionario con claves anidadas.

    Args:
        d: Diccionario a actualizar (por referencia).
        partes: Lista de claves intermedias.
        clave_final: Clave final donde asignar el valor.
    """
    actual = d
    for parte in partes:
        if parte not in actual or not isinstance(actual[parte], dict):
            actual[parte] = {}
        actual = actual[parte]

    actual[clave_final] = None  # placeholder, se asignará el valor real


if __name__ == "__main__":
    # Demostración
    print("=== CARGA DE CONFIGURACIÓN ===")

    # Crear una configuración de ejemplo
    config = {
        "servidor": {
            "host": "localhost",
            "puerto": 8080,
            "protocolo": "https",
        },
        "base_datos": {
            "tipo": "postgresql",
            "conexiones_maximas": 100,
            "timeout": 30,
        },
        "funcionalidades": ["autenticacion", "logging"],
    }

    # Guardar como JSON
    ConfigLoader.guardar("config_ejemplo.json", config)
    print(f"Guardado en: config_ejemplo.json")

    # Cargar y leer
    loader = ConfigLoader(ruta="config_ejemplo.json")
    print(f"\nHost del servidor: {loader['servidor']['host']}")
    print(f"Base de datos: {loader['base_datos']['tipo']}")
    print(f"Funcionalidades: {loader['funcionalidades']}")

    # Validar contra un esquema
    esquema = {
        "servidor.host": {"tipo": str},
        "servidor.puerto": {"tipo": int, "minimo": 1, "maximo": 65535},
        "base_datos.tipo": {"tipo": str, "requerido": True},
    }

    errores = loader.validar(esquema)
    if errores:
        print(f"\nErrores de validación:")
        for error in errores:
            print(f"  ✗ {error}")
    else:
        print("\n✅ Configuración válida.")