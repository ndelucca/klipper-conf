"""Apunta la selección recordada de OrcaSlicer a los perfiles de este repo.

OrcaSlicer.conf guarda qué impresora, proceso y filamento estaban activos al
cerrar. Termina con una línea de checksum:

    # MD5 checksum <hex>

El hash es MD5 del cuerpo con CRLF normalizado a LF y sin newlines finales.
Verificado contra el archivo original antes de escribir nada.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, NamedTuple

MARK = "# MD5 checksum "

type Conf = dict[str, Any]


class ConfFile(NamedTuple):
    """OrcaSlicer.conf leído, con los dos checksums para poder contrastarlos."""

    config: Conf
    declared: str | None
    """El que trae el archivo. None si no tiene línea de checksum."""
    computed: str | None
    """El que sale de recalcularlo. Si difiere, alguien editó el conf a mano."""


def _digest(body: str) -> str:
    return hashlib.md5(
        body.replace("\r\n", "\n").rstrip("\n").encode("utf-8")
    ).hexdigest().upper()


def read(path: Path | str) -> ConfFile:
    """Lee el conf y recalcula su checksum."""
    raw = Path(path).read_text(encoding="utf-8")
    i = raw.rfind(MARK)
    if i < 0:
        return ConfFile(json.loads(raw), None, None)
    body = raw[:i]
    return ConfFile(json.loads(body), raw[i + len(MARK):].strip(), _digest(body))


def write(path: Path | str, cfg: Conf) -> str:
    """Serializa como lo hace OrcaSlicer: tabs, CRLF, checksum al final."""
    body = json.dumps(cfg, indent="\t", ensure_ascii=False, sort_keys=True)
    out = body.replace("\n", "\r\n") + "\r\n" + MARK + _digest(body) + "\r\n"
    Path(path).write_text(out, encoding="utf-8", newline="")
    return _digest(body)


def apply_selection(path: Path | str, printer: str, process: str, filament: str,
                    bed_type: str,
                    keep_system_filaments: list[str]) -> list[str] | None:
    """Deja activa nuestra impresora con su proceso y filamento por defecto.

    Devuelve una lista de líneas describiendo lo que cambió, o None si no hay
    archivo de configuración todavía (instalación nueva: lo crea OrcaSlicer).
    """
    path = Path(path)
    if not path.is_file():
        return None

    cfg, declared, computed = read(path)
    log: list[str] = []
    if declared and computed and declared != computed:
        log.append(f"  aviso: el checksum previo no coincidía "
                   f"({declared} vs {computed}), se reescribe")

    before = cfg.get("filaments", [])
    kept = [f for f in keep_system_filaments if f in before]
    cfg["filaments"] = kept or list(keep_system_filaments)
    log.append(f"  filamentos de sistema visibles: {len(before)} -> "
               f"{len(cfg['filaments'])}")

    entries = cfg.get("orca_presets", [])
    mine = [e for e in entries if e.get("machine") == printer]
    if mine:
        entry = mine[0]
    elif entries:
        entry = dict(entries[0])
        entry["machine"] = printer
    else:
        entry = {"machine": printer}
    entry["filament"] = filament
    entry["process"] = process
    entry["curr_bed_type"] = bed_type
    cfg["orca_presets"] = [entry]
    log.append(f"  selección recordada: {len(entries)} entrada(s) -> 1")

    cfg.setdefault("presets", {})["machine"] = printer

    digest = write(path, cfg)
    _, redeclared, recomputed = read(path)
    ok = redeclared == recomputed == digest
    log.append(f"  checksum MD5: {digest}  {'OK' if ok else 'MISMATCH'}")
    if not ok:
        raise SystemExit("El checksum de OrcaSlicer.conf no verifica.")
    return log
