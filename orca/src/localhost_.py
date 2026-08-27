# -*- coding: utf-8 -*-
"""Resolución del host de impresión, que es lo único local y no versionado.

El repo es público, así que `presets/` guarda siempre un placeholder. La URL
real de la impresora se resuelve al instalar, en este orden:

    1. variable de entorno ORCA_PRINT_HOST
    2. archivo .printer-host en la raiz del repo (ignorado por git)
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

ENV_VAR = "ORCA_PRINT_HOST"
FILE_NAME = ".printer-host"

# Claves del preset de maquina que llevan la URL
HOST_KEYS = ("print_host", "print_host_webui")


def resolve(repo_root):
    """Devuelve (host, origen) o (None, None) si no hay ninguno configurado."""
    env = os.environ.get(ENV_VAR, "").strip()
    if env:
        return env, "variable de entorno %s" % ENV_VAR

    f = repo_root / FILE_NAME
    if f.is_file():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return line, "archivo %s" % FILE_NAME
    return None, None


def apply(rel, text, host, printer_name):
    """Inyecta el host en el JSON del preset de maquina. El resto pasa igual.

    Se usa tanto al instalar como al verificar, para que `verify` no marque una
    diferencia falsa entre el repo (placeholder) y la instalacion (host real).
    """
    if not host or rel != "machine/%s.json" % printer_name:
        return text
    cfg = json.loads(text)
    for k in HOST_KEYS:
        if k in cfg:
            cfg[k] = host
    return json.dumps(cfg, indent=4, ensure_ascii=False) + "\n"
