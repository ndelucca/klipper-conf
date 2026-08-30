"""Resuelve la cadena de herencia de un preset de OrcaSlicer.

Los perfiles de este repo no son autocontenidos: heredan de los presets de
fábrica y solo pisan lo necesario. Para auditar qué valores usa realmente el
laminador hay que resolver esa cadena.

    Printalot PLA @EnderS1Pro
      <- Generic PLA @System <- fdm_filament_pla <- fdm_filament_common
"""

import json
from pathlib import Path
from typing import Any, NamedTuple

from orcakit import orcapaths

type Flat = dict[str, Any]

# Claves que son metadato del preset y no configuración de laminado.
META = frozenset({"inherits", "instantiation", "setting_id", "renamed_from",
                  "is_custom_defined", "from", "type", "version"})


class Resolved(NamedTuple):
    """El preset con la herencia ya aplicada, y de dónde salió cada capa."""

    config: Flat
    chain: list[str]
    """Del más específico al más general: [hijo, padre, abuelo, ...]."""


def search_paths(data: Path | str, kind: str) -> list[Path]:
    """Directorios donde buscar un preset, de más específico a más general."""
    user = orcapaths.user_dir(data)
    system = orcapaths.system_dir(data)
    return {
        "machine": [user / "machine", system / "Custom" / "machine"],
        "process": [user / "process", system / "Custom" / "process"],
        "filament": [user / "filament",
                     system / "OrcaFilamentLibrary" / "filament",
                     system / "OrcaFilamentLibrary" / "filament" / "base",
                     system / "Custom" / "filament"],
    }[kind]


def find(data: Path | str, kind: str, name: str) -> Path:
    for d in search_paths(data, kind):
        p = d / f"{name}.json"
        if p.is_file():
            return p
    raise FileNotFoundError(f"no encuentro {kind}/{name} en {data}")


def resolve(data: Path | str, kind: str, name: str) -> Resolved:
    """Aplana el preset resolviendo toda su cadena de herencia.

    Un preset que se hereda a sí mismo (directa o indirectamente) es un error de
    configuración, no una recursión infinita: se corta con la cadena a la vista.
    """
    chain: list[str] = []

    def walk(current: str) -> Flat:
        if current in chain:
            ciclo = " -> ".join([*chain, current])
            raise ValueError(f"herencia circular en {kind}: {ciclo}")
        raw = json.loads(find(data, kind, current).read_text(encoding="utf-8"))
        chain.append(current)
        parent = raw.get("inherits")
        cfg = walk(parent) if parent else {}
        cfg.update({k: v for k, v in raw.items() if k not in META})
        return cfg

    return Resolved(walk(name), chain)
