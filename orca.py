#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Configuración de OrcaSlicer para Ender 3 S1 Pro + Klipper.

    python orca.py where      dónde está el directorio de datos de OrcaSlicer
    python orca.py build      regenera presets/ desde src/profiles.py
    python orca.py install    instala presets/ en OrcaSlicer (con backup)
    python orca.py verify     compara lo instalado contra presets/
    python orca.py audit      audita caudales y herencia de lo instalado

Sin dependencias externas: solo la librería estándar de Python 3.8+.
Funciona en Windows, macOS y Linux.
"""
import argparse
import datetime
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "src"))

import confpatch          # noqa: E402
import localhost_         # noqa: E402
import orcapaths          # noqa: E402
import profiles           # noqa: E402

PRESETS = REPO / "presets"
KINDS = ("machine", "process", "filament")


def with_local_host(tree):
    """Aplica el host local sobre el snapshot. Devuelve (tree, host, origen).

    El repo es publico: presets/ lleva un placeholder y la URL real solo existe
    en la maquina. Ver src/localhost_.py.
    """
    host, origin = localhost_.resolve(REPO)
    if not host:
        return tree, None, None
    out = {rel: localhost_.apply(rel, text, host, profiles.PRINTER)
           for rel, text in tree.items()}
    return out, host, origin


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def preset_json(cfg):
    """Serialización canónica de un preset. Estable entre corridas y sistemas:
    siempre UTF-8, siempre LF, siempre 4 espacios."""
    return json.dumps(cfg, indent=4, ensure_ascii=False) + "\n"


def info_text(base_id):
    return ("sync_info = \nuser_id = \nsetting_id = \n"
            "base_id = %s\nupdated_time = 0\n" % base_id)


def snapshot():
    """{ruta_relativa: contenido} de todo lo que debe haber en presets/."""
    out = {}
    for kind, name, cfg, base_id in profiles.all_presets():
        out["%s/%s.json" % (kind, name)] = preset_json(cfg)
        out["%s/%s.info" % (kind, name)] = info_text(base_id)
    return out


def read_tree(root):
    out = {}
    for kind in KINDS:
        d = Path(root) / kind
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if p.suffix in (".json", ".info"):
                out["%s/%s" % (kind, p.name)] = p.read_text(encoding="utf-8")
    return out


def same_json(a, b):
    """Compara semánticamente: el orden de claves y el formato no importan."""
    try:
        return json.loads(a) == json.loads(b)
    except (json.JSONDecodeError, TypeError):
        return a == b


def ts():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


# ---------------------------------------------------------------------------
# where
# ---------------------------------------------------------------------------
def cmd_where(args):
    print("Sistema: %s" % sys.platform)
    print("\nCandidatos (en orden):")
    for p in orcapaths.candidates():
        mark = "  <- elegido" if p.is_dir() and orcapaths.looks_like_data_dir(p) else ""
        state = "existe" if p.is_dir() else "no existe"
        print("  [%-9s] %s%s" % (state, p, mark))
    data = orcapaths.data_dir(args.data_dir, require=False)
    print("\nDirectorio de datos : %s" % (data or "NO ENCONTRADO"))
    if data:
        print("Presets de usuario  : %s" % orcapaths.user_dir(data))
        print("Presets de fabrica  : %s" % orcapaths.system_dir(data))
        print("Configuracion       : %s" % orcapaths.conf_path(data))
    running = orcapaths.orca_running()
    print("OrcaSlicer abierto  : %s"
          % {True: "si", False: "no", None: "no se pudo determinar"}[running])
    return 0


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------
def cmd_build(args):
    want = snapshot()
    have = read_tree(PRESETS)

    added = sorted(set(want) - set(have))
    removed = sorted(set(have) - set(want))
    changed = sorted(k for k in set(want) & set(have)
                     if (not same_json(want[k], have[k])
                         if k.endswith(".json") else want[k] != have[k]))

    if args.check:
        if added or removed or changed:
            print("El snapshot en presets/ NO coincide con src/profiles.py:")
            for k in added:
                print("  falta    %s" % k)
            for k in removed:
                print("  sobra    %s" % k)
            for k in changed:
                print("  difiere  %s" % k)
            print("\nCorre 'python orca.py build' y commitea el resultado.")
            return 1
        print("presets/ esta al dia con src/profiles.py (%d archivos)." % len(want))
        return 0

    for kind in KINDS:
        (PRESETS / kind).mkdir(parents=True, exist_ok=True)
    for k in removed:
        (PRESETS / k).unlink()
    for rel, text in want.items():
        (PRESETS / rel).write_text(text, encoding="utf-8", newline="\n")

    if added or removed or changed:
        for k in added:
            print("  nuevo     %s" % k)
        for k in removed:
            print("  eliminado %s" % k)
        for k in changed:
            print("  cambiado  %s" % k)
    print("presets/ regenerado: %d archivos (%d perfiles)."
          % (len(want), len(want) // 2))
    return 0


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------
def cmd_install(args):
    want = snapshot()
    if not (PRESETS / "machine").is_dir():
        print("presets/ no existe todavia. Corriendo build primero.\n")
        cmd_build(argparse.Namespace(check=False))

    have = read_tree(PRESETS)
    stale = [k for k in want if k not in have
             or (not same_json(want[k], have[k]) if k.endswith(".json")
                 else want[k] != have[k])]
    if stale:
        print("AVISO: presets/ esta desactualizado respecto de src/profiles.py.")
        print("       Se instala el contenido de presets/ tal cual.")
        print("       Corre 'python orca.py build' si querias lo otro.\n")

    have, host, origin = with_local_host(have)

    data = orcapaths.data_dir(args.data_dir)
    user = orcapaths.user_dir(data)
    print("Directorio de datos: %s" % data)
    if host:
        print("Host de impresion  : %s  (%s)" % (host, origin))
    else:
        print("Host de impresion  : %s  (placeholder: configura %s o %s)"
              % (profiles.PLACEHOLDER_HOST, localhost_.ENV_VAR,
                 localhost_.FILE_NAME))

    running = orcapaths.orca_running()
    if running and not args.force and not args.dry_run:
        raise SystemExit(
            "\nOrcaSlicer esta abierto. Cerralo antes de instalar: tiene los\n"
            "presets cacheados en memoria y los puede pisar al salir.\n"
            "Para ignorarlo, agrega --force.")
    if running is None:
        print("Aviso: no se pudo verificar si OrcaSlicer esta abierto.")

    if args.dry_run:
        if running:
            print("Aviso: OrcaSlicer esta abierto. Para instalar de verdad,\n"
                  "       cerralo primero.")
        print("\n[dry-run] Se escribirian %d archivos en %s" % (len(have), user))
        for rel in sorted(have):
            dest = user / rel
            state = "sobrescribe" if dest.exists() else "crea       "
            print("  %s %s" % (state, rel))
        loc = user / "_local"
        if loc.is_dir():
            print("  elimina     _local/  (bundles importados)")
        print("\n[dry-run] No se escribio nada.")
        return 0

    # 1. backup de lo que haya
    if user.is_dir() and any(user.iterdir()):
        dest = REPO / "backup" / ts()
        dest.parent.mkdir(exist_ok=True)
        shutil.copytree(user, dest / "user" / "default")
        conf = orcapaths.conf_path(data)
        if conf.is_file():
            shutil.copy2(conf, dest / "OrcaSlicer.conf")
        print("\nBackup de lo anterior: backup/%s/" % dest.name)

    # 2. limpiar presets nuestros y bundles importados
    loc = user / "_local"
    if loc.is_dir():
        shutil.rmtree(loc)
        print("Eliminado: user/default/_local/ (bundles importados)")
    for kind in ("process", "filament"):
        d = user / kind
        if d.is_dir():
            shutil.rmtree(d)

    # 3. escribir
    for kind in KINDS:
        (user / kind).mkdir(parents=True, exist_ok=True)
    for rel, text in sorted(have.items()):
        (user / rel).write_text(text, encoding="utf-8", newline="\n")
    print("Instalados %d archivos (%d perfiles) en %s"
          % (len(have), len(have) // 2, user))

    # 4. dejar la seleccion apuntando a nuestros perfiles
    if args.select:
        log = confpatch.apply_selection(
            orcapaths.conf_path(data),
            profiles.PRINTER, profiles.DEFAULT_PROCESS,
            profiles.DEFAULT_FILAMENT, profiles.DEFAULT_BED_TYPE,
            profiles.KEEP_SYSTEM_FILAMENTS)
        if log is None:
            print("\nNo hay OrcaSlicer.conf todavia: la seleccion se hace a mano\n"
                  "la primera vez que abras OrcaSlicer.")
        else:
            print("\nSeleccion recordada:")
            for line in log:
                print(line)

    print("\nListo. Abri OrcaSlicer y verifica con 'python orca.py verify'.")
    return 0


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------
def cmd_verify(args):
    data = orcapaths.data_dir(args.data_dir)
    user = orcapaths.user_dir(data)
    print("Directorio de datos: %s\n" % data)

    repo = read_tree(PRESETS)
    if not repo:
        raise SystemExit("presets/ esta vacio. Corre 'python orca.py build'.")
    # El host local se aplica tambien aca, si no verify marcaria una diferencia
    # falsa entre el placeholder del repo y la URL real instalada.
    repo, host, origin = with_local_host(repo)
    if host:
        print("Host de impresion esperado: %s  (%s)\n" % (host, origin))

    bad = 0
    for rel in sorted(repo):
        dest = user / rel
        if not dest.is_file():
            print("  FALTA     %s" % rel)
            bad += 1
            continue
        got = dest.read_text(encoding="utf-8")
        ok = same_json(repo[rel], got) if rel.endswith(".json") else repo[rel] == got
        if ok:
            print("  ok        %s" % rel)
        else:
            print("  DIFIERE   %s" % rel)
            bad += 1

    extra = sorted(set(read_tree(user)) - set(repo))
    for rel in extra:
        print("  EXTRA     %s  (no viene de este repo)" % rel)

    loc = user / "_local"
    if loc.is_dir():
        print("  EXTRA     _local/  (bundle importado, ensucia las listas)")

    conf = orcapaths.conf_path(data)
    if conf.is_file():
        cfg, declared, actual = confpatch.read(conf)
        if declared and actual:
            print("\n  checksum OrcaSlicer.conf: %s"
                  % ("ok" if declared == actual else
                     "MISMATCH (%s vs %s)" % (declared, actual)))
        sel = (cfg.get("orca_presets") or [{}])[0]
        print("  seleccion activa: %s / %s / %s"
              % (sel.get("machine", "?"), sel.get("process", "?"),
                 sel.get("filament", "?")))

    print("\n%s" % ("Todo coincide con el repo." if not bad
                    else "%d archivo(s) con diferencias." % bad))
    return 1 if bad else 0


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------
def cmd_audit(args):
    import audit
    return audit.run(orcapaths.data_dir(args.data_dir))


# ---------------------------------------------------------------------------
def main(argv=None):
    # --data-dir se acepta antes o despues del subcomando. SUPPRESS evita que
    # la version del subparser pise a la del parser principal cuando no se pasa.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--data-dir", metavar="RUTA", default=argparse.SUPPRESS,
                        help="directorio de datos de OrcaSlicer "
                             "(default: autodetectado)")

    ap = argparse.ArgumentParser(
        description=__doc__, parents=[common],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("where", parents=[common],
                   help="muestra donde esta OrcaSlicer")

    b = sub.add_parser("build", parents=[common],
                       help="regenera presets/ desde src/profiles.py")
    b.add_argument("--check", action="store_true",
                   help="no escribe: falla si presets/ esta desactualizado")

    i = sub.add_parser("install", parents=[common],
                       help="instala presets/ en OrcaSlicer")
    i.add_argument("--dry-run", action="store_true", help="muestra que haria")
    i.add_argument("--force", action="store_true",
                   help="instala aunque OrcaSlicer este abierto")
    i.add_argument("--no-select", dest="select", action="store_false",
                   help="no toca OrcaSlicer.conf")

    sub.add_parser("verify", parents=[common],
                   help="compara lo instalado contra presets/")
    sub.add_parser("audit", parents=[common],
                   help="audita caudales y herencia")

    args = ap.parse_args(argv)
    if not args.cmd:
        ap.print_help()
        return 0
    args.data_dir = getattr(args, "data_dir", None)
    return {"where": cmd_where, "build": cmd_build, "install": cmd_install,
            "verify": cmd_verify, "audit": cmd_audit}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
