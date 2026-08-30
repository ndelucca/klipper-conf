"""Valida que los presets de OrcaSlicer y la configuración de Klipper sigan
siendo coherentes entre sí.

Las dos mitades de este repo están acopladas: los machine limits del perfil de
impresora son un espejo literal de la sección [printer], el start gcode es un
contrato con la firma del macro START_PRINT, `enable_arc_fitting` depende de
`[gcode_arcs] resolution`, y el pressure advance vive en la tabla `variable_pa`
del macro. Nada de eso lo verifica OrcaSlicer ni Klipper: lo verifica esto.

Lee `profiles.py` directamente, así que no necesita tener OrcaSlicer instalado.
A diferencia de `audit.py`, que audita lo que quedó instalado después de
resolver la herencia, esto compara la FUENTE contra la máquina.
"""

import ast
from pathlib import Path

from orcakit import klippercfg, profiles, values
from orcakit.klippercfg import Config
from orcakit.presets import Filament, Machine, Process
from orcakit.report import Report

# Temperaturas de nozzle de un filamento: las que no pueden pasar el max_temp
# del extruder, y las que no pueden quedar por debajo del min_extrude_temp.
NOZZLE_CEILING_KEYS = ("nozzle_temperature", "nozzle_temperature_initial_layer",
                       "nozzle_temperature_range_high")
NOZZLE_FLOOR_KEYS = ("nozzle_temperature", "nozzle_temperature_initial_layer")

# Duty de ventilador de pieza que pide un filamento.
FAN_KEYS = ("fan_min_speed", "fan_max_speed", "overhang_fan_speed")

# Defaults de Klipper para claves que no se declaran si se usa el valor de
# fábrica. Sin esto una clave ausente parecería un cero.
DEFAULT_SQUARE_CORNER_VELOCITY = 5.0
DEFAULT_MIN_EXTRUDE_TEMP = 170.0
DEFAULT_KICK_START_TIME = 0.1
DEFAULT_OFF_BELOW = 0.0
DEFAULT_ARC_RESOLUTION = 1.0
DEFAULT_FADE_START = 1.0
DEFAULT_FADE_END = 0.0

# Techo de aceleración por encima del cual, sin input shaper, aparece ringing.
#
# Se aplica a las aceleraciones de IMPRESIÓN, no a `[printer] max_accel`. Son
# cosas distintas y confundirlas cuesta velocidad: max_accel es el techo
# mecánico de la máquina, y el travel puede usarlo entero porque el ringing de
# un desplazamiento por el aire no deja marca en la pieza. Lo que hay que
# mantener por debajo de este número es solo la aceleración con la que se
# deposita plástico.
RINGING_ACCEL = 2000

# Las aceleraciones que no depositan plástico, y que por lo tanto quedan fuera
# del presupuesto de ringing. Solo las limita el techo mecánico.
TRAVEL_ACCEL_KEYS = ("travel_acceleration", "initial_layer_travel_acceleration")


def _accels(p: Process) -> dict[str, float]:
    """Aceleraciones absolutas de un proceso, en mm/s2.

    Las relativas ("50%") se saltean: ya son una fracción del techo, así que no
    lo pueden pasar.
    """
    return {k: v for k, raw in p.to_preset().items()
            if k.endswith("_acceleration") and not values.is_pct(raw)
            and (v := values.num(raw)) is not None}


def _print_accels(p: Process) -> dict[str, float]:
    """Solo las que dejan marca en la pieza: las de impresión."""
    return {k: v for k, v in _accels(p).items() if k not in TRAVEL_ACCEL_KEYS}


# Ejes que un G0/G1 puede mover y que tienen límites declarados en Klipper.
MOVE_AXES = ("X", "Y", "Z")


def _macro_moves(body: str) -> list[tuple[str, float]]:
    """(eje, coordenada absoluta) de cada G0/G1 del cuerpo de un macro.

    Se saltean dos cosas, y las dos a propósito:

      - Los movimientos en modo relativo. Después de un G91 un `G1 X5` es un
        desplazamiento, no una posición, y no hay contra qué contrastarlo sin
        saber dónde estaba el carro. END_PRINT usa G91 para el retraction y el
        wipe, y vuelve a G90 antes de presentar la pieza.
      - Los valores interpolados por Jinja (`G1 Z{LAYER}`), que no se pueden
        resolver sin ejecutar el macro.

    Lo que queda son las coordenadas absolutas literales, que es exactamente
    donde estuvo el bug que esto existe para atrapar: la línea de purga en X=2,
    fuera de la malla, y después en X=25, comiéndose el borde de la bandeja.
    """
    out: list[tuple[str, float]] = []
    absolute = True
    for raw in body.splitlines():
        line = raw.split(";")[0].strip().upper()
        if not line:
            continue
        word = line.split()[0]
        if word == "G90":
            absolute = True
            continue
        if word == "G91":
            absolute = False
            continue
        if word not in ("G0", "G1") or not absolute:
            continue
        for token in line.split()[1:]:
            axis, value = token[:1], token[1:]
            if axis in MOVE_AXES and (v := values.num(value)) is not None:
                out.append((axis, v))
    return out


def _area(printable_area: tuple[str, ...] | None) -> tuple[float | None, float | None]:
    """Ancho y largo máximos de un printable_area tipo ("0x0", "250x0", ...)."""
    xs: list[float] = []
    ys: list[float] = []
    for corner in printable_area or ():
        a, _, b = str(corner).partition("x")
        try:
            xs.append(float(a))
            ys.append(float(b))
        except ValueError:
            pass
    return (max(xs) if xs else None), (max(ys) if ys else None)


def _macros(cfg: Config) -> dict[str, dict[str, str]]:
    """{NOMBRE: cuerpo} de los gcode_macro definidos."""
    return {sec.split(" ", 1)[1]: keys for sec, keys in cfg.items()
            if sec.startswith("gcode_macro ")}


def _call(gcode: str | None) -> tuple[str | None, set[str]]:
    """(macro, {parámetros}) de la primera línea de un start/end gcode."""
    lines = (gcode or "").strip().splitlines()
    if not lines or not (parts := lines[0].split()):
        return None, set()
    return parts[0], {p.split("=", 1)[0] for p in parts[1:] if "=" in p}


def _temps(f: Filament, keys: tuple[str, ...]) -> list[float]:
    """Las temperaturas que el filamento declara. Vacío si las hereda todas."""
    return [v for k in keys if (v := values.num(getattr(f, k))) is not None]


def _geometry(r: Report, m: Machine, cfg: Config) -> None:
    r.section("1. GEOMETRIA")
    # printable_area es el área útil de la CHAPA, no el recorrido del carro: el
    # carro llega más lejos que el plato. La relación correcta es que el área
    # declarada ENTRE en el recorrido, no que sea igual.
    ax, ay = _area(m.printable_area)
    r.at_most("printable_area X <= [stepper_x] position_max", ax,
              values.num(cfg.get("stepper_x", {}).get("position_max")))
    r.at_most("printable_area Y <= [stepper_y] position_max", ay,
              values.num(cfg.get("stepper_y", {}).get("position_max")))

    # Cobertura de la malla. Fuera del rectángulo probado Klipper extrapola, así
    # que conviene saber cuánta área imprimible se queda sin dato real.
    mesh = cfg.get("bed_mesh", {})
    mn = values.pair(mesh.get("mesh_min"))
    mx = values.pair(mesh.get("mesh_max"))
    if mn and mx and ax and ay:
        outside = [f"X<{mn[0]:g}" if mn[0] > 0 else "",
                   f"X>{mx[0]:g}" if mx[0] < ax else "",
                   f"Y<{mn[1]:g}" if mn[1] > 0 else "",
                   f"Y>{mx[1]:g}" if mx[1] < ay else ""]
        if outside := [o for o in outside if o]:
            r.warn("cobertura de [bed_mesh] vs printable_area",
                   f"Z extrapolado en {' y '.join(outside)} "
                   f"(malla {mn[0]:g},{mn[1]:g} -> {mx[0]:g},{mx[1]:g})")
        else:
            r.ok("cobertura de [bed_mesh] vs printable_area",
                 "la malla cubre toda el área imprimible")

    extruder = cfg.get("extruder", {})
    r.equal("printable_height = [stepper_z] position_max",
            values.num(m.printable_height),
            values.num(cfg.get("stepper_z", {}).get("position_max")))
    r.equal("nozzle_diameter = [extruder] nozzle_diameter",
            values.num(m.nozzle_diameter),
            values.num(extruder.get("nozzle_diameter")))
    # Un solo diámetro de filamento para todos: si los perfiles no coinciden
    # entre sí, no hay contra qué comparar y eso ya es el error.
    declared = {values.num(f.filament_diameter) for f in profiles.FILAMENTS}
    r.equal("filament_diameter = [extruder] filament_diameter",
            declared.pop() if len(declared) == 1 else None,
            values.num(extruder.get("filament_diameter")))


def _limits(r: Report, m: Machine, cfg: Config) -> None:
    r.section("2. LIMITES DE MOVIMIENTO")
    printer = cfg.get("printer", {})
    kvel = values.num(printer.get("max_velocity"))
    kacc = values.num(printer.get("max_accel"))
    kzvel = values.num(printer.get("max_z_velocity"))
    kzacc = values.num(printer.get("max_z_accel"))
    # Klipper no declara square_corner_velocity si usa el default de 5 mm/s.
    kscv = values.num(printer.get("square_corner_velocity"),
                      DEFAULT_SQUARE_CORNER_VELOCITY)

    for axis in ("x", "y"):
        r.equal(f"machine_max_speed_{axis} = max_velocity",
                values.num(getattr(m, f"machine_max_speed_{axis}")), kvel)
        r.equal(f"machine_max_acceleration_{axis} = max_accel",
                values.num(getattr(m, f"machine_max_acceleration_{axis}")), kacc)
        r.equal(f"machine_max_jerk_{axis} = square_corner_velocity",
                values.num(getattr(m, f"machine_max_jerk_{axis}")), kscv)
    r.equal("machine_max_speed_z = max_z_velocity",
            values.num(m.machine_max_speed_z), kzvel)
    r.equal("machine_max_acceleration_z = max_z_accel",
            values.num(m.machine_max_acceleration_z), kzacc)

    # Ninguna aceleración de ningún proceso puede pedir más que el techo
    # MECÁNICO de la máquina. Acá entra también el travel: max_accel es un
    # límite físico y no lo saltea nadie. El techo de ringing, que es otra
    # cosa y solo aplica a las de impresión, lo valida _input_shaper.
    r.gap()
    for p in profiles.PROCESSES:
        over = [f"{k}={v:g}" for k, v in _accels(p).items()
                if kacc is not None and v > kacc + 1e-9]
        if over:
            r.fail(f"acels de {p.name} <= max_accel", ", ".join(over))
        else:
            r.ok(f"acels de {p.name} <= max_accel", f"techo {kacc:g}")

    r.gap()
    for p in profiles.PROCESSES:
        r.at_most(f"travel_speed_z de {p.name}",
                  values.num(p.travel_speed_z, values.num(m.machine_max_speed_z)),
                  kzvel)


def _thermal(r: Report, cfg: Config) -> None:
    r.section("3. TERMICO Y REFRIGERACION")
    extruder = cfg.get("extruder", {})
    kext = values.num(extruder.get("max_temp"))
    kmin = values.num(extruder.get("min_extrude_temp"), DEFAULT_MIN_EXTRUDE_TEMP)
    kbed = values.num(cfg.get("heater_bed", {}).get("max_temp"))

    for f in profiles.FILAMENTS:
        # Un filamento puede no declarar ninguna temperatura y heredarlas todas
        # del preset de fábrica. Eso no es un error, pero sí algo que decir:
        # acá no hay nada que contrastar contra la máquina.
        if ceiling := _temps(f, NOZZLE_CEILING_KEYS):
            r.at_most(f"nozzle de {f.name} < [extruder] max_temp",
                      max(ceiling), kext)
        else:
            r.warn(f"nozzle de {f.name} < [extruder] max_temp",
                   "no declara temperaturas de nozzle: las hereda de fábrica")

        if floor := _temps(f, NOZZLE_FLOOR_KEYS):
            if kmin is not None and min(floor) < kmin:
                r.fail(f"nozzle de {f.name} >= min_extrude_temp",
                       f"{min(floor):g} < {kmin:g}")

        bed = [v for k, raw in f.to_preset().items()
               if k.endswith(("_plate_temp", "_plate_temp_initial_layer"))
               and (v := values.num(raw)) is not None]
        if bed:
            r.at_most(f"cama de {f.name} < [heater_bed] max_temp", max(bed), kbed)

    # El ventilador de pieza es un cruce real entre las dos mitades: el filamento
    # pide un duty y [fan] decide si a ese duty el ventilador arranca. El ABS
    # pide 15%, y un 4020 desde parado a 15% de PWM no gira: queda energizado,
    # zumbando y sin mover aire.
    fan = cfg.get("fan", {})
    kick = values.num(fan.get("kick_start_time"), DEFAULT_KICK_START_TIME)
    off_below = values.num(fan.get("off_below"), DEFAULT_OFF_BELOW) or 0.0
    r.gap()
    if kick is not None and kick >= 0.3:
        r.ok("[fan] kick_start_time", f"{kick:g} s, alcanza para arrancar a duty bajo")
    else:
        r.warn("[fan] kick_start_time",
               f"{kick:g} s: a duty bajo el ventilador puede no arrancar")

    for f in profiles.FILAMENTS:
        asked = [v for k in FAN_KEYS
                 if (v := values.num(getattr(f, k))) is not None and v > 0]
        if not asked:
            continue
        lowest = min(asked) / 100.0
        if lowest < off_below - 1e-9:
            r.fail(f"duty de ventilador de {f.name} vs [fan] off_below",
                   f"pide {lowest * 100:g}% pero off_below {off_below * 100:g}% "
                   f"lo apaga: ese ajuste no existe")
        else:
            r.ok(f"duty de ventilador de {f.name} vs [fan] off_below",
                 f"mínimo {lowest * 100:g}% > off_below {off_below * 100:g}%")


def _features(r: Report, m: Machine, cfg: Config,
              macros: dict[str, dict[str, str]],
              moonraker: Config | None) -> str | None:
    """Valida las features cruzadas. Devuelve el nombre del macro de arranque."""
    r.section("4. FEATURES")
    if "exclude_object" in cfg:
        using = [p for p in profiles.PROCESSES if values.num(p.exclude_object, 0)]
        r.ok("exclude_object",
             f"[exclude_object] presente, {len(using)} procesos lo usan")
    elif [p for p in profiles.PROCESSES if values.num(p.exclude_object, 0)]:
        r.fail("exclude_object", "los procesos lo piden pero falta [exclude_object]")
    else:
        r.ok("exclude_object", "nadie lo usa")

    kres = values.num(cfg.get("gcode_arcs", {}).get("resolution"),
                      DEFAULT_ARC_RESOLUTION)
    arc = [p for p in profiles.PROCESSES if values.num(p.enable_arc_fitting, 0)]
    if arc and kres is not None and kres > 0.2:
        r.fail("enable_arc_fitting vs [gcode_arcs] resolution",
               f"resolution={kres:g} es demasiado gruesa; facetaría las curvas")
    elif arc:
        r.ok("enable_arc_fitting vs [gcode_arcs] resolution",
             f"{len(arc)} procesos, resolution={kres:g}")
    else:
        r.ok("enable_arc_fitting", "apagado en todos los procesos")

    start, params = _call(m.machine_start_gcode)
    if start not in macros:
        r.fail(f"machine_start_gcode llama a {start}", "el macro no existe")
        return None

    read = klippercfg.macro_params(macros[start].get("gcode", ""))
    if params - read:
        r.fail(f"parámetros de {start}",
               f"Orca manda {sorted(params - read)} que el macro no lee")
    elif read - params:
        r.warn(f"parámetros de {start}",
               f"el macro lee {sorted(read - params)} que Orca no manda "
               f"(usa el default)")
    else:
        r.ok(f"parámetros de {start}", ", ".join(sorted(params)))

    # Moonraker implementa la API de OctoPrint via [octoprint_compat], y el
    # perfil de impresora declara host_type: octoprint porque Orca no tiene un
    # tipo "moonraker". Sin esa sección, todo lo demás valida y el botón de
    # enviar a la impresora simplemente no anda, sin que nada lo explique.
    if (m.host_type or "").lower() == "octoprint":
        if moonraker is None:
            r.warn("host_type octoprint vs [octoprint_compat]",
                   "no hay moonraker.conf en esta versión: sin verificar")
        elif "octoprint_compat" in moonraker:
            r.ok("host_type octoprint vs [octoprint_compat]",
                 "moonraker.conf lo declara")
        else:
            r.fail("host_type octoprint vs [octoprint_compat]",
                   "el perfil habla OctoPrint pero moonraker.conf no declara "
                   "[octoprint_compat]")

    end, _ = _call(m.machine_end_gcode)
    if end in macros:
        r.ok(f"machine_end_gcode llama a {end}", "el macro existe")
    else:
        r.fail(f"machine_end_gcode llama a {end}", "el macro no existe")

    body = macros[start].get("gcode", "")

    # La malla es de la máquina: la carga el macro, no el laminador.
    if "BED_MESH_PROFILE" in (m.machine_start_gcode or ""):
        r.fail("carga de la malla", "está en el start gcode de Orca; va en el macro")
    elif "BED_MESH_PROFILE" in body:
        r.ok("carga de la malla", f"la hace {start}")
    else:
        r.fail("carga de la malla", "no la hace nadie; la malla guardada no se usa")

    # Re-home de Z en caliente. El primer G28 referencia el Z con la cama a
    # temperatura ambiente; para la primera capa la cama subió hasta 100 grados y
    # el bloque otros 60, y todo eso dilata unas décimas. Si alguien saca el G28 Z
    # posterior a la espera de temperatura, el z_offset vuelve a depender del
    # material y nada avisa.
    lines = [l.split(";")[0].strip().upper() for l in body.splitlines()]
    waits = [i for i, l in enumerate(lines)
             if l.startswith(("M109", "M190", "TEMPERATURE_WAIT"))]
    rehomes = [i for i, l in enumerate(lines)
               if l.startswith("G28") and "Z" in l.replace("G28", "")]
    if not waits:
        r.warn("re-home de Z en caliente", f"{start} no espera temperatura")
    elif rehomes and max(rehomes) > max(waits):
        r.ok("re-home de Z en caliente", f"{start} hace G28 Z después de esperar")
    else:
        r.fail("re-home de Z en caliente",
               f"{start} homea el Z solo en frío: el z_offset va a variar con el "
               f"material")

    if "SET_GCODE_OFFSET" in body.upper():
        r.ok("reset del gcode offset", f"{start} arranca desde el z_offset del config")
    else:
        r.warn("reset del gcode offset",
               f"{start} no resetea SET_GCODE_OFFSET: el babystep de la impresión "
               f"anterior sobrevive")

    # Fade de la malla. Sin fade la corrección se suma al Z en TODAS las capas y
    # una pieza alta reproduce la panza de la cama de punta a punta. Klipper
    # deshabilita el fade cuando fade_end <= fade_start, que es el default.
    mesh = cfg.get("bed_mesh", {})
    fs = values.num(mesh.get("fade_start"), DEFAULT_FADE_START)
    fe = values.num(mesh.get("fade_end"), DEFAULT_FADE_END)
    if fs is not None and fe is not None and fe > fs:
        r.ok("[bed_mesh] fade", f"la malla se desvanece entre Z={fs:g} y Z={fe:g}")
    else:
        r.fail("[bed_mesh] fade",
               f"fade_end {fe:g} <= fade_start {fs:g}: la malla corrige a TODA altura")
    return start


def _pressure_advance(r: Report, macros: dict[str, dict[str, str]],
                      start: str | None) -> None:
    r.section("5. PRESSURE ADVANCE")
    raw = macros.get(start or "", {}).get("variable_pa")
    try:
        table = ast.literal_eval(raw) if raw else None
    except (ValueError, SyntaxError):
        table = None
    if not isinstance(table, dict):
        r.fail(f"variable_pa en {start}", "ausente o no es un diccionario")
        return

    r.ok(f"variable_pa en {start}", str(table))
    for f in profiles.FILAMENTS:
        material = values.first(f.filament_type)
        pa = values.num(f.pressure_advance)
        if values.num(f.enable_pressure_advance, 0):
            r.warn(f"PA de {f.name}",
                   f"override deliberado: lo emite Orca ({pa:g}), pisa a Klipper")
        elif material not in table:
            r.fail(f"PA de {f.name}", f"no hay entrada '{material}' en variable_pa")
        elif pa is None or abs(float(table[material]) - pa) > 1e-9:
            r.fail(f"PA de {f.name}",
                   f"orca={pa:g}  klipper={float(table[material]):g}")
        else:
            r.ok(f"PA de {f.name}", f"{material} -> {pa:g}")


def _input_shaper(r: Report, cfg: Config) -> None:
    """El presupuesto de ringing: cuánta aceleración tolera lo que se ve.

    Mira las aceleraciones de IMPRESIÓN de cada proceso, no `max_accel`. La
    versión anterior miraba max_accel y por lo tanto fallaba al subir el techo
    mecánico aunque ninguna aceleración de impresión se hubiera movido, que es
    exactamente lo que hay que poder hacer para que el travel respire.
    """
    r.section("6. INPUT SHAPER")
    kacc = values.num(cfg.get("printer", {}).get("max_accel"))
    techo = f"; max_accel={kacc:g} solo limita el travel" if kacc else ""

    if "input_shaper" in cfg:
        r.ok("[input_shaper]",
             "configurado: las acels de impresion ya no tienen techo de ringing")
        return

    r.ok("[input_shaper]",
         f"sin configurar: techo de ringing {RINGING_ACCEL} "
         f"sobre las acels de impresion{techo}")

    r.gap()
    for p in profiles.PROCESSES:
        over = [f"{k}={v:g}" for k, v in _print_accels(p).items()
                if v > RINGING_ACCEL + 1e-9]
        if over:
            r.fail(f"acels de impresion de {p.name}",
                   f"> {RINGING_ACCEL} sin shaper: " + ", ".join(over))
        else:
            r.ok(f"acels de impresion de {p.name}",
                 f"techo de ringing {RINGING_ACCEL}")


def _macro_geometry(r: Report, cfg: Config,
                    macros: dict[str, dict[str, str]],
                    names: tuple[str, ...]) -> None:
    """Que ningún movimiento absoluto de los macros se salga del recorrido.

    Klipper rechaza el movimiento en tiempo de ejecución con "Move out of
    range", o sea a mitad de una impresión y con el plástico ya puesto. Acá
    cuesta nada y falla antes de desplegar.
    """
    r.section("7. GEOMETRIA DE LOS MACROS")
    limits: dict[str, tuple[float | None, float | None]] = {}
    for axis in MOVE_AXES:
        stepper = cfg.get(f"stepper_{axis.lower()}", {})
        # position_min no se declara si es 0, que es el default de Klipper.
        limits[axis] = (values.num(stepper.get("position_min"), 0.0),
                        values.num(stepper.get("position_max")))

    for name in names:
        if name not in macros:
            continue
        moves = _macro_moves(macros[name].get("gcode", ""))
        if not moves:
            r.warn(f"movimientos de {name}",
                   "no hay ninguna coordenada absoluta literal que revisar")
            continue
        over = []
        for axis, value in moves:
            low, high = limits[axis]
            if low is not None and value < low - 1e-9:
                over.append(f"{axis}{value:g} < position_min {low:g}")
            elif high is not None and value > high + 1e-9:
                over.append(f"{axis}{value:g} > position_max {high:g}")
        if over:
            r.fail(f"movimientos de {name}", ", ".join(sorted(set(over))))
        else:
            r.ok(f"movimientos de {name}",
                 f"{len(moves)} coordenadas, todas dentro del recorrido")


def _process_coherence(r: Report) -> None:
    """Invariantes internas de los procesos, que no dependen de la máquina.

    Viven acá y no en `audit.py` por una razón práctica: audit necesita
    OrcaSlicer instalado para resolver la herencia, así que no corre en CI.
    Esto sí, y es donde tiene que fallar.
    """
    r.section("8. COHERENCIA INTERNA DE LOS PROCESOS")
    for p in profiles.PROCESSES:
        height = values.num(p.layer_height)
        if height is None or height <= 0:
            r.fail(f"altura de capa de {p.name}", "ausente o no numérica")
            continue
        for key in ("support_top_z_distance", "support_bottom_z_distance"):
            gap = values.num(getattr(p, key))
            if gap is None:
                r.warn(f"{key} de {p.name}", "no declarado: lo hereda")
                continue
            # El hueco tiene que ser un número entero de capas de aire. Orca
            # redondea al múltiplo más cercano, así que un valor que no lo sea
            # produce un hueco distinto del declarado y nadie se entera.
            capas = gap / height
            if gap == 0 or abs(capas - round(capas)) < 1e-6:
                r.ok(f"{key} de {p.name}",
                     f"{gap:g} = {round(capas):g} capa"
                     f"{'s' if round(capas) != 1 else ''} de {height:g}")
            else:
                r.fail(f"{key} de {p.name}",
                       f"{gap:g} no es multiplo de la capa {height:g}: "
                       f"Orca lo redondea a {round(capas) * height:g}")


def run(klipper_dir: Path | str) -> Report:
    """Contrasta los presets contra una configuración de Klipper."""
    r = Report()
    r.line(f"Klipper: {klipper_dir}")

    loaded = klippercfg.load_dir(klipper_dir)
    if loaded.missing:
        r.fail("archivos de Klipper", f"faltan: {', '.join(loaded.missing)}")
        return r
    if loaded.clashes:
        r.fail("secciones duplicadas entre archivos", ", ".join(loaded.clashes))
        return r

    cfg = loaded.config
    m = profiles.MACHINE
    macros = _macros(cfg)

    # moonraker.conf es opcional: no todas las versiones lo tienen, y no se
    # mergea con lo demás porque no es configuración de Klipper.
    moonraker_path = Path(klipper_dir) / "moonraker.conf"
    moonraker = (klippercfg.load(moonraker_path)
                 if moonraker_path.is_file() else None)

    _geometry(r, m, cfg)
    _limits(r, m, cfg)
    _thermal(r, cfg)
    start = _features(r, m, cfg, macros, moonraker)
    _pressure_advance(r, macros, start)
    _input_shaper(r, cfg)
    end, _ = _call(m.machine_end_gcode)
    _macro_geometry(r, cfg, macros, tuple(n for n in (start, end) if n))
    _process_coherence(r)

    r.line("")
    r.line("=" * 78)
    if r.failures:
        r.line(f"RESULTADO: {r.failures} incoherencia(s), {r.warnings} aviso(s)")
    else:
        r.line(f"RESULTADO: las dos mitades coinciden. {r.warnings} aviso(s).")
    r.line("=" * 78)
    return r
