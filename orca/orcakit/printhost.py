"""Resolución del host de impresión, que es lo único local y no versionado.

El repo es público, así que `presets/` guarda siempre un placeholder. La URL
real de la impresora se resuelve al instalar, en este orden:

    1. variable de entorno ORCA_PRINT_HOST
    2. archivo .printer-host en la raíz del repo (ignorado por git)
    3. nada: queda el placeholder de profiles.PLACEHOLDER_HOST

Por qué no versionarla: una instancia de Moonraker publicada en internet suele
quedar sin autenticación efectiva, porque el reverse proxy cae dentro de
`trusted_clients` y entonces Moonraker trata como confiable a todo request que
entre por el dominio. Con esa API abierta se puede mandar gcode arbitrario,
subir o borrar archivos y apagar la máquina. Lo único que protege es que nadie
conozca la URL, y un repo público la deja indexada.
"""

import json
import os
from pathlib import Path
from typing import NamedTuple

ENV_VAR = "ORCA_PRINT_HOST"
FILE_NAME = ".printer-host"

# Claves del preset de máquina que llevan la URL.
HOST_KEYS = ("print_host", "print_host_webui")


class PrintHost(NamedTuple):
    """El host resuelto y de dónde salió, para poder decírselo al usuario."""

    url: str | None
    origin: str | None


def resolve(repo_root: Path | str) -> PrintHost:
    """Busca el host local. Devuelve (None, None) si no hay ninguno configurado."""
    if env := os.environ.get(ENV_VAR, "").strip():
        return PrintHost(env, f"variable de entorno {ENV_VAR}")

    f = Path(repo_root) / FILE_NAME
    if f.is_file():
        for raw in f.read_text(encoding="utf-8").splitlines():
            if (line := raw.strip()) and not line.startswith("#"):
                return PrintHost(line, f"archivo {FILE_NAME}")
    return PrintHost(None, None)


def apply(rel: str, text: str, host: str | None, printer_name: str) -> str:
    """Inyecta el host en el JSON del preset de máquina. El resto pasa igual.

    Se usa tanto al instalar como al verificar, para que `verify` no marque una
    diferencia falsa entre el repo (placeholder) y la instalación (host real).
    """
    if not host or rel != f"machine/{printer_name}.json":
        return text
    cfg = json.loads(text)
    for k in HOST_KEYS:
        if k in cfg:
            cfg[k] = host
    return json.dumps(cfg, indent=4, ensure_ascii=False, sort_keys=True) + "\n"
