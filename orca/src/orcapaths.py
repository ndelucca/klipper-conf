# -*- coding: utf-8 -*-
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


def candidates():
    """Rutas donde puede estar el directorio de datos, en orden de preferencia."""
    home = Path.home()
    out = []

    env = os.environ.get(ENV_VAR)
    if env:
        out.append(Path(env).expanduser())

    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            out.append(Path(appdata) / "OrcaSlicer")
        out.append(home / "AppData" / "Roaming" / "OrcaSlicer")
    elif sys.platform == "darwin":
        out.append(home / "Library" / "Application Support" / "OrcaSlicer")
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        out.append(Path(xdg).expanduser() / "OrcaSlicer" if xdg
                   else home / ".config" / "OrcaSlicer")
        out.append(home / ".var" / "app" /
                   "io.github.softfever.OrcaSlicer" / "config" / "OrcaSlicer")
        out.append(home / "snap" / "orcaslicer" / "current" / ".config" / "OrcaSlicer")

    # sin duplicados, preservando el orden
    seen, uniq = set(), []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def looks_like_data_dir(p):
    """Un directorio de datos real tiene el bundle de presets de sistema."""
    return (p / "system").is_dir() or (p / "OrcaSlicer.conf").is_file()


def data_dir(explicit=None, require=True):
    """Devuelve el directorio de datos de OrcaSlicer.

    explicit  ruta forzada por el usuario (--data-dir). Se valida pero no se
              descarta: si el usuario la pide, se usa.
    require   si no se encuentra nada, levanta SystemExit con un mensaje útil.
    """
    if explicit:
        p = Path(explicit).expanduser()
        if require and not p.is_dir():
            raise SystemExit("El --data-dir indicado no existe: %s" % p)
        return p

    for p in candidates():
        if p.is_dir() and looks_like_data_dir(p):
            return p
    for p in candidates():
        if p.is_dir():
            return p

    if not require:
        return None
    raise SystemExit(
        "No encuentro el directorio de datos de OrcaSlicer.\n"
        "Buscado en:\n  " + "\n  ".join(str(p) for p in candidates()) +
        "\n\nPasalo a mano con --data-dir RUTA, o exportá %s." % ENV_VAR)


def user_dir(data):
    """Donde viven los presets de usuario."""
    return Path(data) / "user" / "default"


def system_dir(data):
    """Donde viven los presets de fábrica que heredamos."""
    return Path(data) / "system"


def conf_path(data):
    return Path(data) / "OrcaSlicer.conf"


def orca_running():
    """True / False, o None si no se pudo determinar.

    Escribir presets con OrcaSlicer abierto no rompe nada de inmediato, pero la
    app los tiene cacheados en memoria y los puede pisar al cerrarse.
    """
    names = ("orca-slicer", "orcaslicer")
    try:
        if sys.platform == "win32":
            cmd = ["tasklist", "/fo", "csv", "/nh"]
        else:
            cmd = ["ps", "-A", "-o", "comm="]
        out = subprocess.run(cmd, capture_output=True, text=True,
                             timeout=30).stdout.lower()
        return any(n in out for n in names)
    except Exception:
        return None
