# -*- coding: utf-8 -*-
"""Valida que los presets de OrcaSlicer y la configuracion de Klipper sigan
siendo coherentes entre si.

Las dos mitades de este repo estan acopladas: los machine limits del perfil de
impresora son un espejo literal de la seccion [printer], el start gcode es un
contrato con la firma del macro START_PRINT, `enable_arc_fitting` depende de
`[gcode_arcs] resolution`, y el pressure advance vive en la tabla `variable_pa`
del macro. Nada de eso lo verifica OrcaSlicer ni Klipper: lo verifica esto.

Lee `profiles.py` directamente, asi que no necesita tener OrcaSlicer instalado.
A diferencia de `audit.py`, que audita lo que quedo instalado despues de
resolver la herencia, esto compara la FUENTE contra la maquina.
"""
import ast

import klippercfg
import profiles

BAR = "=" * 78


def _num(v):
    """Primer numero de un valor de Orca (string, lista, o porcentaje)."""
    if isinstance(v, list):
        v = v[0] if v else None
    if v is None:
        return None
    try:
        return float(str(v).replace("%", ""))
    except ValueError:
        return None


def _es_pct(v):
    if isinstance(v, list):
        v = v[0] if v else ""
    return str(v).endswith("%")


def _area(printable_area):
    """Ancho y largo maximos de un printable_area tipo ["0x0","250x0",...]."""
    xs, ys = [], []
    for p in printable_area:
        a, _, b = str(p).partition("x")
        try:
            xs.append(float(a))
            ys.append(float(b))
        except ValueError:
            pass
    return (max(xs) if xs else None), (max(ys) if ys else None)


def _par(v):
    """(x, y) de un valor Klipper tipo "20, 5"."""
    if v is None:
        return None
    partes = str(v).split(",")
    if len(partes) != 2:
        return None
    try:
        return float(partes[0]), float(partes[1])
    except ValueError:
        return None


def _gcode_macros(cfg):
    """{NOMBRE: cuerpo} de los gcode_macro definidos."""
    out = {}
    for sec, keys in cfg.items():
        if sec.startswith("gcode_macro "):
            out[sec.split(" ", 1)[1]] = keys
    return out


def _llamada(gcode):
    """(macro, {parametros}) de la primera linea de un start/end gcode."""
    linea = (gcode or "").strip().splitlines()
    if not linea:
        return None, set()
    partes = linea[0].split()
    if not partes:
        return None, set()
    return partes[0], {p.split("=", 1)[0] for p in partes[1:] if "=" in p}


class Informe(object):
    def __init__(self):
        self.fallos = 0
        self.avisos = 0

    def seccion(self, titulo):
        print("")
        print(BAR)
        print(titulo)
        print(BAR)

    def ok(self, que, detalle=""):
        print("  ok      %-44s %s" % (que, detalle))

    def falla(self, que, detalle):
        print("  FALLA   %-44s %s" % (que, detalle))
        self.fallos += 1

    def aviso(self, que, detalle):
        print("  aviso   %-44s %s" % (que, detalle))
        self.avisos += 1

    def igual(self, que, a, b, detalle=""):
        if a is None or b is None:
            self.falla(que, "falta un lado (orca=%s klipper=%s)" % (a, b))
        elif abs(a - b) < 1e-9:
            self.ok(que, detalle or "%g" % a)
        else:
            self.falla(que, "orca=%g  klipper=%g" % (a, b))

    def menor_igual(self, que, a, b, detalle=""):
        if a is None or b is None:
            self.falla(que, "falta un lado (orca=%s klipper=%s)" % (a, b))
        elif a <= b + 1e-9:
            self.ok(que, detalle or "%g <= %g" % (a, b))
        else:
            self.falla(que, "%g excede el limite %g" % (a, b))


def run(klipper_dir):
    cfg, faltantes, choques = klippercfg.load_dir(klipper_dir)
    print("Klipper: %s" % klipper_dir)
    if faltantes:
        print("  FALTAN archivos: %s" % ", ".join(faltantes))
        return 1
    if choques:
        print("  SECCIONES DUPLICADAS entre archivos: %s" % ", ".join(choques))
        return 1

    m = profiles.MACHINE
    r = Informe()
    macros = _gcode_macros(cfg)

    # ------------------------------------------------------------------
    r.seccion("1. GEOMETRIA")
    # printable_area es el area util de la CHAPA, no el recorrido del carro:
    # el carro llega mas lejos que el plato. La relacion correcta es que el
    # area declarada ENTRE en el recorrido, no que sea igual.
    ax, ay = _area(m["printable_area"])
    px = klippercfg.num(cfg.get("stepper_x", {}).get("position_max"))
    py = klippercfg.num(cfg.get("stepper_y", {}).get("position_max"))
    r.menor_igual("printable_area X <= [stepper_x] position_max", ax, px)
    r.menor_igual("printable_area Y <= [stepper_y] position_max", ay, py)

    # Cobertura de la malla. Fuera del rectangulo probado Klipper extrapola,
    # asi que conviene saber cuanta area imprimible se queda sin dato real.
    mesh = cfg.get("bed_mesh", {})
    mn = _par(mesh.get("mesh_min"))
    mx = _par(mesh.get("mesh_max"))
    if mn and mx and ax and ay:
        fuera = []
        if mn[0] > 0:
            fuera.append("X<%g" % mn[0])
        if mx[0] < ax:
            fuera.append("X>%g" % mx[0])
        if mn[1] > 0:
            fuera.append("Y<%g" % mn[1])
        if mx[1] < ay:
            fuera.append("Y>%g" % mx[1])
        if fuera:
            r.aviso("cobertura de [bed_mesh] vs printable_area",
                    "Z extrapolado en %s (malla %g,%g -> %g,%g)"
                    % (" y ".join(fuera), mn[0], mn[1], mx[0], mx[1]))
        else:
            r.ok("cobertura de [bed_mesh] vs printable_area",
                 "la malla cubre toda el area imprimible")

    r.igual("printable_height = [stepper_z] position_max",
            _num(m["printable_height"]),
            klippercfg.num(cfg.get("stepper_z", {}).get("position_max")))
    r.igual("nozzle_diameter = [extruder] nozzle_diameter",
            _num(m["nozzle_diameter"]),
            klippercfg.num(cfg.get("extruder", {}).get("nozzle_diameter")))
    fdia = {_num(f["filament_diameter"]) for f in profiles.FILAMENTS}
    r.igual("filament_diameter = [extruder] filament_diameter",
            fdia.pop() if len(fdia) == 1 else None,
            klippercfg.num(cfg.get("extruder", {}).get("filament_diameter")))

    # ------------------------------------------------------------------
    r.seccion("2. LIMITES DE MOVIMIENTO")
    pr = cfg.get("printer", {})
    kvel = klippercfg.num(pr.get("max_velocity"))
    kacc = klippercfg.num(pr.get("max_accel"))
    kzvel = klippercfg.num(pr.get("max_z_velocity"))
    kzacc = klippercfg.num(pr.get("max_z_accel"))
    # Klipper no declara square_corner_velocity si usa el default de 5 mm/s.
    kscv = klippercfg.num(pr.get("square_corner_velocity"), 5.0)

    for eje in ("x", "y"):
        r.igual("machine_max_speed_%s = max_velocity" % eje,
                _num(m["machine_max_speed_" + eje]), kvel)
        r.igual("machine_max_acceleration_%s = max_accel" % eje,
                _num(m["machine_max_acceleration_" + eje]), kacc)
        r.igual("machine_max_jerk_%s = square_corner_velocity" % eje,
                _num(m["machine_max_jerk_" + eje]), kscv)
    r.igual("machine_max_speed_z = max_z_velocity",
            _num(m["machine_max_speed_z"]), kzvel)
    r.igual("machine_max_acceleration_z = max_z_accel",
            _num(m["machine_max_acceleration_z"]), kzacc)

    print("")
    for p in profiles.PROCESSES:
        malas = []
        for k, v in p.items():
            if not k.endswith("_acceleration") or _es_pct(v):
                continue
            val = _num(v)
            if val is not None and val > kacc + 1e-9:
                malas.append("%s=%g" % (k, val))
        if malas:
            r.falla("acels de %s <= max_accel" % p["name"], ", ".join(malas))
        else:
            r.ok("acels de %s <= max_accel" % p["name"], "techo %g" % kacc)

    print("")
    for p in profiles.PROCESSES:
        r.menor_igual("travel_speed_z de %s" % p["name"],
                      _num(p.get("travel_speed_z", m.get("machine_max_speed_z"))),
                      kzvel)

    # ------------------------------------------------------------------
    r.seccion("3. TERMICO Y REFRIGERACION")
    kext = klippercfg.num(cfg.get("extruder", {}).get("max_temp"))
    kmin = klippercfg.num(cfg.get("extruder", {}).get("min_extrude_temp"), 170.0)
    kbed = klippercfg.num(cfg.get("heater_bed", {}).get("max_temp"))
    for f in profiles.FILAMENTS:
        nom = f["name"]
        temps = [_num(f[k]) for k in ("nozzle_temperature",
                                      "nozzle_temperature_initial_layer",
                                      "nozzle_temperature_range_high")
                 if k in f]
        temps = [t for t in temps if t is not None]
        r.menor_igual("nozzle de %s < [extruder] max_temp" % nom,
                      max(temps), kext)
        bajas = [_num(f[k]) for k in ("nozzle_temperature",
                                      "nozzle_temperature_initial_layer") if k in f]
        bajas = [t for t in bajas if t is not None]
        if min(bajas) < kmin:
            r.falla("nozzle de %s >= min_extrude_temp" % nom,
                    "%g < %g" % (min(bajas), kmin))
        cama = [_num(v) for k, v in f.items()
                if k.endswith("_plate_temp") or k.endswith("_plate_temp_initial_layer")]
        cama = [t for t in cama if t is not None]
        if cama:
            r.menor_igual("cama de %s < [heater_bed] max_temp" % nom,
                          max(cama), kbed)

    # El ventilador de pieza es un cruce real entre las dos mitades: el
    # filamento pide un duty y [fan] decide si a ese duty el ventilador
    # arranca. El ABS pide 15%, y un 4020 desde parado a 15% de PWM no gira:
    # queda energizado, zumbando y sin mover aire.
    print("")
    fan = cfg.get("fan", {})
    kick = klippercfg.num(fan.get("kick_start_time"), 0.1)
    off = klippercfg.num(fan.get("off_below"), 0.0)
    if kick >= 0.3:
        r.ok("[fan] kick_start_time", "%g s, alcanza para arrancar a duty bajo" % kick)
    else:
        r.aviso("[fan] kick_start_time",
                "%g s: a duty bajo el ventilador puede no arrancar" % kick)
    for f in profiles.FILAMENTS:
        pedidos = [_num(f[k]) for k in ("fan_min_speed", "fan_max_speed",
                                        "overhang_fan_speed") if k in f]
        pedidos = [v for v in pedidos if v is not None and v > 0]
        if not pedidos:
            continue
        menor = min(pedidos) / 100.0
        if menor < off - 1e-9:
            r.falla("duty de ventilador de %s vs [fan] off_below" % f["name"],
                    "pide %g%% pero off_below %g%% lo apaga: ese ajuste no existe"
                    % (menor * 100, off * 100))
        else:
            r.ok("duty de ventilador de %s vs [fan] off_below" % f["name"],
                 "minimo %g%% > off_below %g%%" % (menor * 100, off * 100))

    # ------------------------------------------------------------------
    r.seccion("4. FEATURES")
    if "exclude_object" in cfg:
        usan = [p["name"] for p in profiles.PROCESSES
                if str(_num(p.get("exclude_object", "0"))) == "1.0"]
        r.ok("exclude_object", "[exclude_object] presente, %d procesos lo usan" % len(usan))
    else:
        malos = [p["name"] for p in profiles.PROCESSES if _num(p.get("exclude_object", "0"))]
        if malos:
            r.falla("exclude_object", "los procesos lo piden pero falta [exclude_object]")
        else:
            r.ok("exclude_object", "nadie lo usa")

    kres = klippercfg.num(cfg.get("gcode_arcs", {}).get("resolution"), 1.0)
    arc = [p["name"] for p in profiles.PROCESSES if _num(p.get("enable_arc_fitting", "0"))]
    if arc and kres > 0.2:
        r.falla("enable_arc_fitting vs [gcode_arcs] resolution",
                "resolution=%g es demasiado gruesa; facetaria las curvas" % kres)
    elif arc:
        r.ok("enable_arc_fitting vs [gcode_arcs] resolution",
             "%d procesos, resolution=%g" % (len(arc), kres))
    else:
        r.ok("enable_arc_fitting", "apagado en todos los procesos")

    mac, params = _llamada(m["machine_start_gcode"])
    if mac not in macros:
        r.falla("machine_start_gcode llama a %s" % mac, "el macro no existe")
    else:
        leidos = klippercfg.macro_params(macros[mac].get("gcode", ""))
        if params - leidos:
            r.falla("parametros de %s" % mac,
                    "Orca manda %s que el macro no lee" % sorted(params - leidos))
        elif leidos - params:
            r.aviso("parametros de %s" % mac,
                    "el macro lee %s que Orca no manda (usa el default)"
                    % sorted(leidos - params))
        else:
            r.ok("parametros de %s" % mac, ", ".join(sorted(params)))

    endm, _ = _llamada(m["machine_end_gcode"])
    if endm in macros:
        r.ok("machine_end_gcode llama a %s" % endm, "el macro existe")
    else:
        r.falla("machine_end_gcode llama a %s" % endm, "el macro no existe")

    # La malla es de la maquina: la carga el macro, no el laminador.
    en_orca = "BED_MESH_PROFILE" in m["machine_start_gcode"]
    en_macro = "BED_MESH_PROFILE" in macros.get(mac, {}).get("gcode", "")
    if en_orca:
        r.falla("carga de la malla", "esta en el start gcode de Orca; va en el macro")
    elif en_macro:
        r.ok("carga de la malla", "la hace %s" % mac)
    else:
        r.falla("carga de la malla", "no la hace nadie; la malla guardada no se usa")

    # Re-home de Z en caliente. El primer G28 referencia el Z con la cama a
    # temperatura ambiente; para la primera capa la cama subio hasta 100 grados
    # y el bloque otros 60, y todo eso dilata unas decimas. Si alguien saca el
    # G28 Z posterior a la espera de temperatura, el z_offset vuelve a depender
    # del material y nada avisa.
    cuerpo = macros.get(mac, {}).get("gcode", "")
    lineas = [l.split(";")[0].strip().upper() for l in cuerpo.splitlines()]
    espera = [i for i, l in enumerate(lineas)
              if l.startswith("M109") or l.startswith("M190")
              or l.startswith("TEMPERATURE_WAIT")]
    rehome = [i for i, l in enumerate(lineas)
              if l.startswith("G28") and "Z" in l.replace("G28", "")]
    if not espera:
        r.aviso("re-home de Z en caliente", "%s no espera temperatura" % mac)
    elif rehome and max(rehome) > max(espera):
        r.ok("re-home de Z en caliente", "%s hace G28 Z despues de esperar" % mac)
    else:
        r.falla("re-home de Z en caliente",
                "%s homea el Z solo en frio: el z_offset va a variar con el "
                "material" % mac)

    if "SET_GCODE_OFFSET" in cuerpo.upper():
        r.ok("reset del gcode offset", "%s arranca desde el z_offset del config" % mac)
    else:
        r.aviso("reset del gcode offset",
                "%s no resetea SET_GCODE_OFFSET: el babystep de la impresion "
                "anterior sobrevive" % mac)

    # Fade de la malla. Sin fade la correccion se suma al Z en TODAS las capas
    # y una pieza alta reproduce la panza de la cama de punta a punta. Klipper
    # deshabilita el fade cuando fade_end <= fade_start, que es el default.
    fs = klippercfg.num(mesh.get("fade_start"), 1.0)
    fe = klippercfg.num(mesh.get("fade_end"), 0.0)
    if fe > fs:
        r.ok("[bed_mesh] fade", "la malla se desvanece entre Z=%g y Z=%g" % (fs, fe))
    else:
        r.falla("[bed_mesh] fade",
                "fade_end %g <= fade_start %g: la malla corrige a TODA altura"
                % (fe, fs))

    # ------------------------------------------------------------------
    r.seccion("5. PRESSURE ADVANCE")
    crudo = macros.get(mac, {}).get("variable_pa")
    try:
        tabla = ast.literal_eval(crudo) if crudo else None
    except (ValueError, SyntaxError):
        tabla = None
    if not isinstance(tabla, dict):
        r.falla("variable_pa en %s" % mac, "ausente o no es un diccionario")
    else:
        r.ok("variable_pa en %s" % mac, str(tabla))
        for f in profiles.FILAMENTS:
            nom, tipo = f["name"], f["filament_type"][0]
            pa = _num(f.get("pressure_advance"))
            if _num(f.get("enable_pressure_advance", "0")):
                r.aviso("PA de %s" % nom,
                        "override deliberado: lo emite Orca (%g), pisa a Klipper" % pa)
                continue
            if tipo not in tabla:
                r.falla("PA de %s" % nom, "no hay entrada '%s' en variable_pa" % tipo)
            elif abs(float(tabla[tipo]) - pa) > 1e-9:
                r.falla("PA de %s" % nom,
                        "orca=%g  klipper=%g" % (pa, float(tabla[tipo])))
            else:
                r.ok("PA de %s" % nom, "%s -> %g" % (tipo, pa))

    # ------------------------------------------------------------------
    r.seccion("6. INPUT SHAPER")
    if "input_shaper" in cfg:
        r.ok("[input_shaper]", "configurado; max_accel puede subir de 2000")
    elif kacc > 2000:
        r.falla("[input_shaper]",
                "no configurado pero max_accel=%g > 2000: va a haber ringing" % kacc)
    else:
        r.ok("[input_shaper]",
             "sin configurar, max_accel=%g se mantiene en el techo seguro" % kacc)

    # ------------------------------------------------------------------
    print("")
    print(BAR)
    if r.fallos:
        print("RESULTADO: %d incoherencia(s), %d aviso(s)" % (r.fallos, r.avisos))
    else:
        print("RESULTADO: las dos mitades coinciden. %d aviso(s)." % r.avisos)
    print(BAR)
    return 1 if r.fallos else 0
