"""Construcción y comparación del snapshot de `presets/`.

`presets/` es el snapshot exacto que consume OrcaSlicer, y se versiona por dos
motivos: que el repo sirva aunque nunca corras `build`, y que los diffs de git
muestren el cambio real de configuración de cada commit.

Acá vive el invariante central del repo —cuándo dos versiones del snapshot son
la misma— que antes estaba escrito tres veces a mano en el CLI, una por comando,
con la forma `not same_json(a, b) if k.endswith(".json") else a != b`. Todo lo de
este módulo es puro: no lee ni escribe nada salvo `read()`, y no imprime.
"""

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from orcakit import profiles

type Tree = dict[str, str]
"""Ruta relativa dentro de presets/ -> contenido del archivo."""


class Kind(StrEnum):
    """Los tres tipos de preset, que son también los subdirectorios."""

    MACHINE = "machine"
    PROCESS = "process"
    FILAMENT = "filament"


@dataclass(frozen=True, slots=True)
class Diff:
    """Qué separa a dos snapshots. Vacío es falsy: `if diff(a, b):`."""

    added: list[str]
    removed: list[str]
    changed: list[str]

    def __bool__(self) -> bool:
        return bool(self.added or self.removed or self.changed)


def preset_json(cfg: dict) -> str:
    """Serialización canónica de un preset. Estable entre corridas y sistemas:
    siempre UTF-8, siempre LF, siempre 4 espacios, siempre claves ordenadas.

    `sort_keys` desacopla el snapshot del orden en que `profiles.py` declara los
    valores: el JSON no cambia aunque la fuente se reordene, así que los diffs de
    git muestran solo cambios reales de configuración.
    """
    return json.dumps(cfg, indent=4, ensure_ascii=False, sort_keys=True) + "\n"


def info_text(base_id: str) -> str:
    """El .info que OrcaSlicer guarda al lado de cada preset para rastrear de
    qué preset de fábrica deriva."""
    return ("sync_info = \nuser_id = \nsetting_id = \n"
            f"base_id = {base_id}\nupdated_time = 0\n")


def build() -> Tree:
    """Todo lo que debe haber en presets/, construido desde profiles.py."""
    out: Tree = {}
    for e in profiles.all_presets():
        out[f"{e.kind}/{e.name}.json"] = preset_json(e.config)
        out[f"{e.kind}/{e.name}.info"] = info_text(e.base_id)
    return out


def read(root: Path | str) -> Tree:
    """Lee un árbol de presets del disco. Ignora lo que no sea .json ni .info."""
    out: Tree = {}
    for kind in Kind:
        d = Path(root) / kind
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if p.suffix in (".json", ".info"):
                out[f"{kind}/{p.name}"] = p.read_text(encoding="utf-8")
    return out


def equal(rel: str, a: str, b: str) -> bool:
    """Si dos versiones del mismo archivo dicen lo mismo.

    Los .json se comparan semánticamente: el orden de las claves y el formato no
    cambian lo que OrcaSlicer lee, y una instalación previa puede haberlos
    reescrito con otro estilo. Los .info son cinco líneas de texto plano y se
    comparan literales.
    """
    if not rel.endswith(".json"):
        return a == b
    try:
        return json.loads(a) == json.loads(b)
    except (json.JSONDecodeError, TypeError):
        return a == b


def diff(want: Tree, have: Tree) -> Diff:
    """Qué le falta, le sobra y difiere a `have` respecto de `want`."""
    return Diff(
        added=sorted(set(want) - set(have)),
        removed=sorted(set(have) - set(want)),
        changed=sorted(k for k in set(want) & set(have)
                       if not equal(k, want[k], have[k])),
    )
