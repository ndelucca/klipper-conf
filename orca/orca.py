#!/usr/bin/env python3
"""Configuración de OrcaSlicer para Ender 3 S1 Pro + Klipper.

    python orca/orca.py where    dónde está el directorio de datos de OrcaSlicer
    python orca/orca.py build    regenera presets/ desde orcakit/profiles.py
    python orca/orca.py install  instala presets/ en OrcaSlicer (con backup)
    python orca/orca.py verify   compara lo instalado contra presets/
    python orca/orca.py audit    audita caudales y herencia de lo instalado
    python orca/orca.py check    valida los presets contra versions/<CURRENT>

`build --check` y `check` son cosas distintas: el primero detecta que presets/
quedó desactualizado respecto de profiles.py, el segundo que los presets dejaron
de ser coherentes con la configuración de Klipper de la impresora.

Sin dependencias externas: solo la librería estándar de Python 3.14.
"""

import argparse
import datetime
import shutil
import sys
from pathlib import Path

# HERE es esta carpeta (la mitad "slicer" del repo); REPO es la raíz, donde
# convive con versions/ (la mitad "Klipper") y donde vive .printer-host.
# Al ejecutar este script Python ya pone HERE en sys.path, así que `orcakit` se
# importa sin tocar nada.
HERE = Path(__file__).resolve().parent
REPO = HERE.parent

from orcakit import (audit, checkcfg, confpatch, orcapaths, printhost,  # noqa: E402
                     profiles, report, snapshot)
from orcakit.snapshot import Kind  # noqa: E402

PRESETS = HERE / "presets"


def with_local_host(tree: snapshot.Tree) -> tuple[snapshot.Tree, str | None, str | None]:
    """Aplica el host local sobre el snapshot. Devuelve (tree, host, origen).

    El repo es público: presets/ lleva un placeholder y la URL real solo existe
    en la máquina. Ver orcakit/printhost.py.
    """
    host, origin = printhost.resolve(REPO)
    if not host:
        return tree, None, None
    return ({rel: printhost.apply(rel, text, host, profiles.PRINTER)
             for rel, text in tree.items()}, host, origin)


def timestamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


# ---------------------------------------------------------------------------
# where
# ---------------------------------------------------------------------------
def cmd_where(args: argparse.Namespace) -> int:
    print(f"Sistema: {sys.platform}")
    print("\nCandidatos (en orden):")
    for p in orcapaths.candidates():
        chosen = "  <- elegido" if p.is_dir() and orcapaths.looks_like_data_dir(p) else ""
        state = "existe" if p.is_dir() else "no existe"
        print(f"  [{state:<9}] {p}{chosen}")

    data = orcapaths.data_dir(args.data_dir, require=False)
    print(f"\nDirectorio de datos : {data or 'NO ENCONTRADO'}")
    if data:
        print(f"Presets de usuario  : {orcapaths.user_dir(data)}")
        print(f"Presets de fabrica  : {orcapaths.system_dir(data)}")
        print(f"Configuracion       : {orcapaths.conf_path(data)}")

    running = {True: "si", False: "no", None: "no se pudo determinar"}
    print(f"OrcaSlicer abierto  : {running[orcapaths.orca_running()]}")
    return 0


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------
def write_presets() -> snapshot.Diff:
    """Vuelca el snapshot a presets/. Devuelve qué cambió."""
    want = snapshot.build()
    changes = snapshot.diff(want, snapshot.read(PRESETS))
    for kind in Kind:
        (PRESETS / kind).mkdir(parents=True, exist_ok=True)
    for rel in changes.removed:
        (PRESETS / rel).unlink()
    for rel, text in want.items():
        (PRESETS / rel).write_text(text, encoding="utf-8", newline="\n")
    return changes


def cmd_build(args: argparse.Namespace) -> int:
    want = snapshot.build()

    if args.check:
        changes = snapshot.diff(want, snapshot.read(PRESETS))
        if not changes:
            print(f"presets/ esta al dia con orcakit/profiles.py "
                  f"({len(want)} archivos).")
            return 0
        print("El snapshot en presets/ NO coincide con orcakit/profiles.py:")
        for rel in changes.added:
            print(f"  falta    {rel}")
        for rel in changes.removed:
            print(f"  sobra    {rel}")
        for rel in changes.changed:
            print(f"  difiere  {rel}")
        print("\nCorre 'python orca/orca.py build' y commitea el resultado.")
        return 1

    changes = write_presets()
    for rel in changes.added:
        print(f"  nuevo     {rel}")
    for rel in changes.removed:
        print(f"  eliminado {rel}")
    for rel in changes.changed:
        print(f"  cambiado  {rel}")
    print(f"presets/ regenerado: {len(want)} archivos ({len(want) // 2} perfiles).")
    return 0


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------
def cmd_install(args: argparse.Namespace) -> int:
    want = snapshot.build()
    if not (PRESETS / Kind.MACHINE).is_dir():
        print("presets/ no existe todavia. Corriendo build primero.\n")
        write_presets()

    have = snapshot.read(PRESETS)
    if snapshot.diff(want, have):
        print("AVISO: presets/ esta desactualizado respecto de orcakit/profiles.py.")
        print("       Se instala el contenido de presets/ tal cual.")
        print("       Corre 'python orca/orca.py build' si querias lo otro.\n")

    have, host, origin = with_local_host(have)

    data = orcapaths.data_dir(args.data_dir)
    user = orcapaths.user_dir(data)
    print(f"Directorio de datos: {data}")
    if host:
        print(f"Host de impresion  : {host}  ({origin})")
    else:
        print(f"Host de impresion  : {profiles.PLACEHOLDER_HOST}  "
              f"(placeholder: configura {printhost.ENV_VAR} o {printhost.FILE_NAME})")

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
        print(f"\n[dry-run] Se escribirian {len(have)} archivos en {user}")
        for rel in sorted(have):
            state = "sobrescribe" if (user / rel).exists() else "crea       "
            print(f"  {state} {rel}")
        if (user / "_local").is_dir():
            print("  elimina     _local/  (bundles importados)")
        print("\n[dry-run] No se escribio nada.")
        return 0

    # 1. backup de lo que haya
    if user.is_dir() and any(user.iterdir()):
        dest = REPO / "backup" / timestamp()
        dest.parent.mkdir(exist_ok=True)
        shutil.copytree(user, dest / "user" / "default")
        conf = orcapaths.conf_path(data)
        if conf.is_file():
            shutil.copy2(conf, dest / "OrcaSlicer.conf")
        print(f"\nBackup de lo anterior: backup/{dest.name}/")

    # 2. limpiar presets nuestros y bundles importados.
    #    machine/ NO se borra a proposito: ahi pueden convivir perfiles de otras
    #    impresoras del usuario, que este repo no gestiona. Los nuestros se
    #    pisan igual al escribirlos en el paso 3.
    if (loc := user / "_local").is_dir():
        shutil.rmtree(loc)
        print("Eliminado: user/default/_local/ (bundles importados)")
    for kind in (Kind.PROCESS, Kind.FILAMENT):
        if (d := user / kind).is_dir():
            shutil.rmtree(d)

    # 3. escribir
    for kind in Kind:
        (user / kind).mkdir(parents=True, exist_ok=True)
    for rel, text in sorted(have.items()):
        (user / rel).write_text(text, encoding="utf-8", newline="\n")
    print(f"Instalados {len(have)} archivos ({len(have) // 2} perfiles) en {user}")

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
            print("\n".join(log))

    print("\nListo. Abri OrcaSlicer y verifica con 'python orca/orca.py verify'.")
    return 0


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------
def cmd_verify(args: argparse.Namespace) -> int:
    data = orcapaths.data_dir(args.data_dir)
    user = orcapaths.user_dir(data)
    print(f"Directorio de datos: {data}\n")

    repo = snapshot.read(PRESETS)
    if not repo:
        raise SystemExit("presets/ esta vacio. Corre 'python orca/orca.py build'.")
    # El host local se aplica tambien aca: si no, verify marcaria una diferencia
    # falsa entre el placeholder del repo y la URL real instalada.
    repo, host, origin = with_local_host(repo)
    if host:
        print(f"Host de impresion esperado: {host}  ({origin})\n")

    bad = 0
    for rel in sorted(repo):
        dest = user / rel
        if not dest.is_file():
            print(f"  FALTA     {rel}")
            bad += 1
        elif snapshot.equal(rel, repo[rel], dest.read_text(encoding="utf-8")):
            print(f"  ok        {rel}")
        else:
            print(f"  DIFIERE   {rel}")
            bad += 1

    for rel in sorted(set(snapshot.read(user)) - set(repo)):
        print(f"  EXTRA     {rel}  (no viene de este repo)")
    if (user / "_local").is_dir():
        print("  EXTRA     _local/  (bundle importado, ensucia las listas)")

    conf = orcapaths.conf_path(data)
    if conf.is_file():
        cfg, declared, computed = confpatch.read(conf)
        if declared and computed:
            state = "ok" if declared == computed else f"MISMATCH ({declared} vs {computed})"
            print(f"\n  checksum OrcaSlicer.conf: {state}")
        sel = (cfg.get("orca_presets") or [{}])[0]
        print(f"  seleccion activa: {sel.get('machine', '?')} / "
              f"{sel.get('process', '?')} / {sel.get('filament', '?')}")

    print(f"\n{'Todo coincide con el repo.' if not bad else f'{bad} archivo(s) con diferencias.'}")
    return 1 if bad else 0


# ---------------------------------------------------------------------------
# audit / check
# ---------------------------------------------------------------------------
def cmd_audit(args: argparse.Namespace) -> int:
    result = audit.run(orcapaths.data_dir(args.data_dir))
    print(report.render(result))
    return result.exit_code


def klipper_dir(args: argparse.Namespace) -> Path:
    """Directorio de configuracion de Klipper contra el que validar.

    Por defecto, la version que declara versions/CURRENT, que es la unica fuente
    de verdad de cual esta viva. El rol klipper_config de nd.homelab lee el mismo
    archivo.
    """
    if args.klipper_dir:
        return Path(args.klipper_dir)
    marca = REPO / "versions" / "CURRENT"
    if not marca.is_file():
        raise SystemExit(f"No existe {marca}. Usa --klipper-dir.")
    version = marca.read_text(encoding="utf-8").strip()
    d = REPO / "versions" / version
    if not d.is_dir():
        raise SystemExit(f"versions/CURRENT dice '{version}' pero {d} no existe.")
    return d


def cmd_check(args: argparse.Namespace) -> int:
    result = checkcfg.run(klipper_dir(args))
    print(report.render(result))
    return result.exit_code


# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    # --data-dir se acepta antes o despues del subcomando. SUPPRESS evita que la
    # version del subparser pise a la del parser principal cuando no se pasa.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--data-dir", metavar="RUTA", default=argparse.SUPPRESS,
                        help="directorio de datos de OrcaSlicer "
                             "(default: autodetectado)")

    ap = argparse.ArgumentParser(
        description=__doc__, parents=[common],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("where", parents=[common],
                   help="muestra donde esta OrcaSlicer").set_defaults(run=cmd_where)

    b = sub.add_parser("build", parents=[common],
                       help="regenera presets/ desde orcakit/profiles.py")
    b.add_argument("--check", action="store_true",
                   help="no escribe: falla si presets/ esta desactualizado")
    b.set_defaults(run=cmd_build)

    i = sub.add_parser("install", parents=[common],
                       help="instala presets/ en OrcaSlicer")
    i.add_argument("--dry-run", action="store_true", help="muestra que haria")
    i.add_argument("--force", action="store_true",
                   help="instala aunque OrcaSlicer este abierto")
    i.add_argument("--no-select", dest="select", action="store_false",
                   help="no toca OrcaSlicer.conf")
    i.set_defaults(run=cmd_install)

    sub.add_parser("verify", parents=[common],
                   help="compara lo instalado contra presets/").set_defaults(run=cmd_verify)
    sub.add_parser("audit", parents=[common],
                   help="audita caudales y herencia").set_defaults(run=cmd_audit)

    c = sub.add_parser("check", parents=[common],
                       help="valida los presets contra la config de Klipper")
    c.add_argument("--klipper-dir", metavar="RUTA", default=None,
                   help="default: versions/<CURRENT>")
    c.set_defaults(run=cmd_check)
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    if not args.cmd:
        ap.print_help()
        return 0
    args.data_dir = getattr(args, "data_dir", None)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
