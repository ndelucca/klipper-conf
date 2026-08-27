# -*- coding: utf-8 -*-
"""Resuelve la cadena de herencia de un preset de OrcaSlicer.

Los perfiles de este repo no son autocontenidos: heredan de los presets de
fábrica y solo pisan lo necesario. Para auditar qué valores usa realmente el
laminador hay que resolver esa cadena.

    Printalot PLA @EnderS1Pro
      <- Generic PLA @System <- fdm_filament_pla <- fdm_filament_common
"""
import json
from pathlib import Path

import orcapaths

# Claves que son metadato del preset y no configuración de laminado.
META = {"inherits", "instantiation", "setting_id", "renamed_from",
        "is_custom_defined", "from", "type", "version"}


def search_paths(data, kind):
    """Directorios donde buscar un preset, de más específico a más general."""
    user = orcapaths.user_dir(data)
    sysd = orcapaths.system_dir(data)
    return {
        "machine": [user / "machine", sysd / "Custom" / "machine"],
        "process": [user / "process", sysd / "Custom" / "process"],
        "filament": [user / "filament",
                     sysd / "OrcaFilamentLibrary" / "filament",
                     sysd / "OrcaFilamentLibrary" / "filament" / "base",
                     sysd / "Custom" / "filament"],
    }[kind]


def find(data, kind, name):
    for d in search_paths(data, kind):
        p = Path(d) / (name + ".json")
        if p.is_file():
            return p
    raise FileNotFoundError("no encuentro %s/%s en %s" % (kind, name, data))


def resolve(data, kind, name, _chain=None):
    """Devuelve (config_plano, cadena_de_herencia)."""
    chain = _chain if _chain is not None else []
    j = json.loads(find(data, kind, name).read_text(encoding="utf-8"))
    chain.append(name)
    parent = j.get("inherits")
    cfg = resolve(data, kind, parent, chain)[0] if parent else {}
    cfg.update({k: v for k, v in j.items() if k not in META})
    return cfg, chain
