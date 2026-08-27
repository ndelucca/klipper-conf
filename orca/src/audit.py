# -*- coding: utf-8 -*-
"""Auditoría de los valores FINALES (post-herencia) de los perfiles instalados.

Comprueba dos cosas que no se ven mirando los JSON del repo:

  1. Que ningún valor agresivo del preset de fábrica @MyKlipper haya
     sobrevivido a la herencia. Ese preset apunta a una CoreXY con input
     shaper y pide 200 mm/s y 5000 mm/s2.
  2. Que el caudal volumétrico que pide cada proceso entre en el techo que
     declara cada filamento.
"""
import flatten
import profiles

# Valores que vienen de fdm_process_klipper_common y DEBEN estar pisados
HERENCIA_PELIGROSA = {
    "default_acceleration": 5000, "top_surface_acceleration": 3000,
    "travel_acceleration": 7000, "inner_wall_acceleration": 5000,
    "outer_wall_acceleration": 3000, "initial_layer_speed": 50,
    "initial_layer_infill_speed": 105, "outer_wall_speed": 120,
    "inner_wall_speed": 200, "internal_solid_infill_speed": 200,
    "top_surface_speed": 100, "gap_infill_speed": 100,
    "sparse_infill_speed": 200, "travel_speed": 350,
}

FEATURES = [
    ("Pared exterior", "outer_wall_speed", "outer_wall_line_width"),
    ("Pared interior", "inner_wall_speed", "inner_wall_line_width"),
    ("Relleno solido", "internal_solid_infill_speed", "internal_solid_infill_line_width"),
    ("Relleno disperso", "sparse_infill_speed", "sparse_infill_line_width"),
    ("Sup. superior", "top_surface_speed", "top_surface_line_width"),
]

BAR = "=" * 78


def _num(v):
    if isinstance(v, list):
        v = v[0]
    return float(str(v).replace("%", ""))


def run(data):
    """Devuelve 0 si todo está bien, 1 si algo falla."""
    procs = [p["name"] for p in profiles.PROCESSES]
    fils = [f["name"] for f in profiles.FILAMENTS]
    fallos = 0

    print(BAR)
    print("1. HERENCIA: ningun valor agresivo de fabrica debe sobrevivir")
    print(BAR)
    for pn in procs:
        cfg, _ = flatten.resolve(data, "process", pn)
        malos = [k for k, bad in HERENCIA_PELIGROSA.items()
                 if _num(cfg.get(k, 0)) >= bad]
        fallos += len(malos)
        print("  %-30s %s" % (pn, "OK" if not malos
                              else "HEREDADO: " + ", ".join(malos)))
    print("\n  -> %d valores agresivos sobrevivieron\n" % fallos)

    print(BAR)
    print("2. CAUDAL VOLUMETRICO por proceso (mm3/s)")
    print(BAR)
    caudales = {}
    for pn in procs:
        cfg, _ = flatten.resolve(data, "process", pn)
        lh = _num(cfg["layer_height"])
        print("\n  %s   (altura de capa %.2f mm)" % (pn, lh))
        mx = 0.0
        for label, sk, wk in FEATURES:
            s, w = _num(cfg[sk]), _num(cfg[wk])
            q = lh * w * s
            mx = max(mx, q)
            print("    %-18s %5.0f mm/s x %.2f mm  ->  %5.2f mm3/s"
                  % (label, s, w, q))
        caudales[pn] = mx
        print("    %-18s                        MAXIMO %5.2f mm3/s" % ("", mx))

    print("\n" + BAR)
    print("3. CONTRASTE contra el limite de caudal de cada filamento")
    print(BAR)
    print("   (si el proceso pide mas, Orca frena las velocidades solo)")
    lim = {}
    for fn in fils:
        cfg, _ = flatten.resolve(data, "filament", fn)
        lim[fn] = _num(cfg["filament_max_volumetric_speed"])
    print("\n%-30s" % "proceso" + "".join("%12s" % f.split()[1] for f in fils))
    print("%-30s" % "limite mm3/s" + "".join("%12.1f" % lim[f] for f in fils))
    print("-" * 78)
    for pn in procs:
        row = "%-30s" % pn.replace(" " + profiles.SUF, "")
        for fn in fils:
            row += "%12s" % ("%.1f %s" % (caudales[pn],
                             "ok" if caudales[pn] <= lim[fn] else "FRENA"))
        print(row)

    print("\n" + BAR)
    print("4. RETRACCION Y TEMPERATURAS por filamento")
    print(BAR)
    print("%-22s %5s %5s %5s %7s %8s %9s"
          % ("filamento", "nozz", "1ra", "cama", "caudal", "retrac", "fan m/M"))
    mach, _ = flatten.resolve(data, "machine", profiles.PRINTER)
    for fn in fils:
        c, _ = flatten.resolve(data, "filament", fn)
        rl = c.get("filament_retraction_length", ["nil"])[0]
        if rl == "nil":
            rl = mach["retraction_length"][0] + "*"
        print("%-22s %5s %5s %5s %7s %8s %5s/%s" % (
            fn.replace("Printalot ", "").replace(" " + profiles.SUF, ""),
            c["nozzle_temperature"][0], c["nozzle_temperature_initial_layer"][0],
            c["hot_plate_temp"][0], c["filament_max_volumetric_speed"][0], rl,
            c["fan_min_speed"][0], c["fan_max_speed"][0]))
    print("\n  * = hereda la retraccion de la impresora")
    return 1 if fallos else 0
