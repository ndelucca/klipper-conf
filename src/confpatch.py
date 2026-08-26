# -*- coding: utf-8 -*-
"""Apunta la selección recordada de OrcaSlicer a los perfiles de este repo.

OrcaSlicer.conf guarda qué impresora, proceso y filamento estaban activos al
cerrar. Termina con una línea de checksum:

    # MD5 checksum <hex>

El hash es MD5 del cuerpo con CRLF normalizado a LF y sin newlines finales.
Verificado contra el archivo original antes de escribir nada.
"""
import hashlib
import json

MARK = "# MD5 checksum "


def _digest(body_text):
    return hashlib.md5(
        body_text.replace("\r\n", "\n").rstrip("\n").encode("utf-8")
    ).hexdigest().upper()


def read(path):
    """Devuelve (config, checksum_declarado, checksum_calculado)."""
    raw = path.read_text(encoding="utf-8")
    i = raw.rfind(MARK)
    if i < 0:
        return json.loads(raw), None, None
    body = raw[:i]
    declared = raw[i + len(MARK):].strip()
    return json.loads(body), declared, _digest(body)


def write(path, cfg):
    """Serializa como lo hace OrcaSlicer: tabs, CRLF, checksum al final."""
    body = json.dumps(cfg, indent="\t", ensure_ascii=False, sort_keys=True)
    out = body.replace("\n", "\r\n") + "\r\n" + MARK + _digest(body) + "\r\n"
    path.write_text(out, encoding="utf-8", newline="")
    return _digest(body)


def apply_selection(path, printer, process, filament, bed_type,
                    keep_system_filaments):
    """Deja activa nuestra impresora con su proceso y filamento por defecto.

    Devuelve una lista de líneas describiendo lo que cambió, o None si no hay
    archivo de configuración todavía (instalación nueva: lo crea OrcaSlicer).
    """
    if not path.is_file():
        return None

    cfg, declared, actual = read(path)
    log = []
    if declared and actual and declared != actual:
        log.append("  aviso: el checksum previo no coincidia "
                   "(%s vs %s), se reescribe" % (declared, actual))

    before = cfg.get("filaments", [])
    kept = [f for f in keep_system_filaments if f in before]
    cfg["filaments"] = kept or list(keep_system_filaments)
    log.append("  filamentos de sistema visibles: %d -> %d"
               % (len(before), len(cfg["filaments"])))

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
    log.append("  seleccion recordada: %d entrada(s) -> 1" % len(entries))

    cfg.setdefault("presets", {})["machine"] = printer

    digest = write(path, cfg)
    _, redeclared, recomputed = read(path)
    ok = redeclared == recomputed == digest
    log.append("  checksum MD5: %s  %s" % (digest, "OK" if ok else "MISMATCH"))
    if not ok:
        raise SystemExit("El checksum de OrcaSlicer.conf no verifica.")
    return log
