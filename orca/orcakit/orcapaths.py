"""Localización cross-platform del directorio de datos de OrcaSlicer.

OrcaSlicer guarda su configuración en distinto lugar según el sistema:

    Windows   %APPDATA%\\OrcaSlicer
    macOS     ~/Library/Application Support/OrcaSlicer
    Linux     $XDG_CONFIG_HOME/OrcaSlicer  (o ~/.config/OrcaSlicer)
    Flatpak   ~/.var/app/io.github.softfever.OrcaSlicer/config/OrcaSlicer

Se puede forzar con la variable de entorno ORCA_DATA_DIR o con --data-dir.
"""

import os
import subprocess
import sys
from pathlib import Path

ENV_VAR = "ORCA_DATA_DIR"

# Nombres del ejecutable de OrcaSlicer, para detectar si está corriendo.
PROCESS_NAMES = ("orca-slicer", "orcaslicer")


def candidates() -> list[Path]:
    """Rutas donde puede estar el directorio de datos, en orden de preferencia."""
    home = Path.home()
    out: list[Path] = []

    if env := os.environ.get(ENV_VAR):
        out.append(Path(env).expanduser())

    match sys.platform:
        case "win32":
            if appdata := os.environ.get("APPDATA"):
                out.append(Path(appdata) / "OrcaSlicer")
            out.append(home / "AppData" / "Roaming" / "OrcaSlicer")
        case "darwin":
            out.append(home / "Library" / "Application Support" / "OrcaSlicer")
        case _:
            xdg = os.environ.get("XDG_CONFIG_HOME")
            out.append(Path(xdg).expanduser() / "OrcaSlicer" if xdg
                       else home / ".config" / "OrcaSlicer")
            out.append(home / ".var" / "app"
                       / "io.github.softfever.OrcaSlicer" / "config" / "OrcaSlicer")
            out.append(home / "snap" / "orcaslicer" / "current"
                       / ".config" / "OrcaSlicer")

    return list(dict.fromkeys(out))  # sin duplicados, preservando el orden


def looks_like_data_dir(p: Path) -> bool:
    """Un directorio de datos real tiene el bundle de presets de sistema."""
    return (p / "system").is_dir() or (p / "OrcaSlicer.conf").is_file()


def data_dir(explicit: str | Path | None = None, require: bool = True) -> Path | None:
    """Devuelve el directorio de datos de OrcaSlicer.

    explicit  ruta forzada por el usuario (--data-dir). Se valida pero no se
              descarta: si el usuario la pide, se usa.
    require   si no se encuentra nada, levanta SystemExit con un mensaje útil.
    """
    if explicit:
        p = Path(explicit).expanduser()
        if require and not p.is_dir():
            raise SystemExit(f"El --data-dir indicado no existe: {p}")
        return p

    found = candidates()
    for p in found:
        if p.is_dir() and looks_like_data_dir(p):
            return p
    for p in found:
        if p.is_dir():
            return p

    if not require:
        return None
    listed = "\n  ".join(str(p) for p in found)
    raise SystemExit(
        "No encuentro el directorio de datos de OrcaSlicer.\n"
        f"Buscado en:\n  {listed}\n\n"
        f"Pasalo a mano con --data-dir RUTA, o exportá {ENV_VAR}.")


def user_dir(data: Path | str) -> Path:
    """Donde viven los presets de usuario."""
    return Path(data) / "user" / "default"


def system_dir(data: Path | str) -> Path:
    """Donde viven los presets de fábrica que heredamos."""
    return Path(data) / "system"


def conf_path(data: Path | str) -> Path:
    return Path(data) / "OrcaSlicer.conf"


def orca_running() -> bool | None:
    """True / False, o None si no se pudo determinar.

    Escribir presets con OrcaSlicer abierto no rompe nada de inmediato, pero la
    app los tiene cacheados en memoria y los puede pisar al cerrarse.

    Solo se traga los errores de ejecutar el comando: cualquier otra excepción
    es un bug de acá y tiene que verse.
    """
    cmd = (["tasklist", "/fo", "csv", "/nh"] if sys.platform == "win32"
           else ["ps", "-A", "-o", "comm="])
    try:
        out = subprocess.run(cmd, capture_output=True, text=True,
                             timeout=30).stdout.lower()
    except (OSError, subprocess.SubprocessError):
        return None
    return any(name in out for name in PROCESS_NAMES)
