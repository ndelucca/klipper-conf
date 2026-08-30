"""Auditoría de los valores FINALES (post-herencia) de los perfiles instalados.

Comprueba dos cosas que no se ven mirando los JSON del repo:

  1. Que ningún valor agresivo del preset de fábrica @MyKlipper haya sobrevivido
     a la herencia. Ese preset apunta a una CoreXY con input shaper y pide
     200 mm/s y 5000 mm/s2.
  2. Que el caudal volumétrico que pide cada proceso entre en el techo que
     declara cada filamento.

A diferencia de `checkcfg.py`, que lee la fuente, esto lee lo que quedó
instalado y resuelve su cadena de herencia: es la única forma de ver los valores
con los que el laminador realmente trabaja.
"""

from pathlib import Path

from orcakit import flatten, profiles, values
from orcakit.report import Report

# Valores que vienen de fdm_process_klipper_common y DEBEN estar pisados.
FACTORY_AGGRESSIVE = {
    "default_acceleration": 5000, "top_surface_acceleration": 3000,
    "travel_acceleration": 7000, "inner_wall_acceleration": 5000,
    "outer_wall_acceleration": 3000, "initial_layer_speed": 50,
    "initial_layer_infill_speed": 105, "outer_wall_speed": 120,
    "inner_wall_speed": 200, "internal_solid_infill_speed": 200,
    "top_surface_speed": 100, "gap_infill_speed": 100,
    "sparse_infill_speed": 200, "travel_speed": 350,
}

# (etiqueta, clave de velocidad, clave de ancho de línea) por feature.
FEATURES = (
    ("Pared exterior", "outer_wall_speed", "outer_wall_line_width"),
    ("Pared interior", "inner_wall_speed", "inner_wall_line_width"),
    ("Relleno solido", "internal_solid_infill_speed", "internal_solid_infill_line_width"),
    ("Relleno disperso", "sparse_infill_speed", "sparse_infill_line_width"),
    ("Sup. superior", "top_surface_speed", "top_surface_line_width"),
)


def _inheritance(r: Report, data: Path | str) -> None:
    r.section("1. HERENCIA: ningun valor agresivo de fabrica debe sobrevivir")
    for p in profiles.PROCESSES:
        cfg = flatten.resolve(data, "process", p.name).config
        survived = [k for k, ceiling in FACTORY_AGGRESSIVE.items()
                    if (values.num(cfg.get(k), 0.0) or 0.0) >= ceiling]
        if survived:
            r.fail(p.name, "HEREDADO: " + ", ".join(survived))
        else:
            r.ok(p.name, "ningun valor de fabrica sobrevivio")


def _flows(r: Report, data: Path | str) -> dict[str, float]:
    """Caudal volumétrico máximo que pide cada proceso, en mm3/s."""
    r.section("2. CAUDAL VOLUMETRICO por proceso (mm3/s)")
    peak: dict[str, float] = {}
    for p in profiles.PROCESSES:
        cfg = flatten.resolve(data, "process", p.name).config
        height = values.require(cfg.get("layer_height"), f"layer_height de {p.name}")
        r.line("")
        r.line(f"  {p.name}   (altura de capa {height:.2f} mm)")
        highest = 0.0
        for label, speed_key, width_key in FEATURES:
            speed = values.require(cfg.get(speed_key), f"{speed_key} de {p.name}")
            width = values.require(cfg.get(width_key), f"{width_key} de {p.name}")
            flow = height * width * speed
            highest = max(highest, flow)
            r.line(f"    {label:<18} {speed:5.0f} mm/s x {width:.2f} mm  "
                   f"->  {flow:5.2f} mm3/s")
        peak[p.name] = highest
        r.line(f"    {'':<18}                        MAXIMO {highest:5.2f} mm3/s")
    return peak


def _ceilings(r: Report, data: Path | str, peak: dict[str, float]) -> None:
    r.section("3. CONTRASTE contra el limite de caudal de cada filamento")
    r.line("   (si el proceso pide mas, Orca frena las velocidades solo)")
    limit = {
        f.name: values.require(
            flatten.resolve(data, "filament", f.name).config.get(
                "filament_max_volumetric_speed"),
            f"filament_max_volumetric_speed de {f.name}")
        for f in profiles.FILAMENTS
    }
    r.line("")
    short = [f.name.split()[1] for f in profiles.FILAMENTS]
    r.line(f"{'proceso':<30}" + "".join(f"{s:>12}" for s in short))
    r.line(f"{'limite mm3/s':<30}"
           + "".join(f"{limit[f.name]:>12.1f}" for f in profiles.FILAMENTS))
    r.line("-" * 78)
    for p in profiles.PROCESSES:
        cells = "".join(
            f"{f'{peak[p.name]:.1f} ' + ('ok' if peak[p.name] <= limit[f.name] else 'FRENA'):>12}"
            for f in profiles.FILAMENTS)
        r.line(f"{p.name.replace(' ' + profiles.SUF, ''):<30}{cells}")


def _materials(r: Report, data: Path | str) -> None:
    r.section("4. RETRACCION Y TEMPERATURAS por filamento")
    r.line(f"{'filamento':<22} {'nozz':>5} {'1ra':>5} {'cama':>5} {'caudal':>7} "
           f"{'retrac':>8} {'fan m/M':>9}")
    machine = flatten.resolve(data, "machine", profiles.PRINTER).config
    for f in profiles.FILAMENTS:
        cfg = flatten.resolve(data, "filament", f.name).config
        retract = values.first(cfg.get("filament_retraction_length", ["nil"]))
        if retract == "nil":
            # El filamento no pisa la retracción: usa la de la impresora.
            retract = f"{values.first(machine.get('retraction_length'))}*"
        label = f.name.replace("Printalot ", "").replace(" " + profiles.SUF, "")
        def field(key: str) -> str:
            """El valor tal cual, o el nombre de lo que falta: una tabla con un
            hueco silencioso es peor que una que dice qué no encontró."""
            got = values.first(cfg.get(key))
            return got if got is not None else f"<sin {key}>"

        r.line(f"{label:<22} "
               f"{field('nozzle_temperature'):>5} "
               f"{field('nozzle_temperature_initial_layer'):>5} "
               f"{field('hot_plate_temp'):>5} "
               f"{field('filament_max_volumetric_speed'):>7} "
               f"{retract:>8} "
               f"{field('fan_min_speed'):>5}/{field('fan_max_speed')}")
    r.line("")
    r.line("  * = hereda la retraccion de la impresora")


def run(data: Path | str) -> Report:
    """Audita los perfiles instalados en un directorio de datos de OrcaSlicer."""
    r = Report()
    _inheritance(r, data)
    _ceilings(r, data, _flows(r, data))
    _materials(r, data)
    return r
