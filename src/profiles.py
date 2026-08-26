# -*- coding: utf-8 -*-
"""Definición de los perfiles de OrcaSlicer para Ender 3 S1 Pro + Klipper.

Este archivo es la FUENTE DE VERDAD de toda la configuración. No escribe nada:
solo construye las estructuras. `orca.py build` las vuelca a presets/ y
`orca.py install` las copia al directorio de datos de OrcaSlicer.

Para cambiar algo de forma permanente: editar acá, correr `orca.py build`, y
commitear el cambio junto con el snapshot regenerado.

Contexto de hardware (leído de printer.cfg vía Moonraker, 2026-08-26):

    Cinemática     cartesian (bed slinger)
    Área útil      X 250 x Y 235 x Z 270 mm
    Extrusor       Sprite Pro direct drive, gear ratio 42:12
    Hotend         bimetálico, max_temp 300
    Cama           max_temp 110
    max_velocity   300 mm/s
    max_accel      2000 mm/s2   <- techo real de todas las aceleraciones
    max_z_velocity   5 mm/s
    [input_shaper]     NO CONFIGURADO
    pressure_advance   NO CONFIGURADO
"""

PRINTER = "EnderS1ProKlipper"
SUF = "@EnderS1Pro"
VER = "2.4.0.1"
COMPAT = [PRINTER]

# La URL real de la impresora NO se versiona. Este placeholder es lo que queda
# en presets/, y `orca.py install` lo reemplaza por el host local si hay uno
# configurado (variable ORCA_PRINT_HOST o archivo .printer-host).
#
# Motivo: una instancia de Moonraker expuesta a internet suele quedar sin
# autenticacion real, porque el reverse proxy cae dentro de trusted_clients y
# entonces todo request entrante se considera confiable. Publicar la URL en un
# repo publico es entregar una API que acepta gcode arbitrario.
PLACEHOLDER_HOST = "http://printer.local"

# setting_id de los presets de fábrica de los que deriva cada uno. OrcaSlicer
# lo guarda en el .info y lo usa para rastrear la herencia.
BASE_IDS = {
    "MyKlipper 0.4 nozzle": "h7lWobw9IAl6rIFf",
    "0.12mm Fine @MyKlipper": "guUxwo1j4TPACM0Z",
    "0.20mm Standard @MyKlipper": "UkxcnbdZ2LeRvO4x",
    "0.28mm Extra Draft @MyKlipper": "Wxgntm1oFqaS5sSD",
    "Generic PLA @System": "RcBNzytWgwRrwXXz",
    "Generic PETG @System": "YiQZfhL6hH0giSHL",
    "Generic ABS @System": "W0LP8Ah5MHMzogvV",
    "Generic TPU @System": "D6O8IcmSe8WGqOvb",
}


# ============================================================================
# IMPRESORA
# ============================================================================
# BED_MESH_PROFILE LOAD=default es necesario porque START_PRINT hace G28, que
# borra la malla activa, y la macro nunca la vuelve a cargar. Sin esta línea la
# malla 6x6 guardada en printer.cfg no se usa en ninguna impresión.
START = ("START_PRINT BED_TEMP=[bed_temperature_initial_layer_single] "
         "EXTRUDER_TEMP=[nozzle_temperature_initial_layer]\n"
         "BED_MESH_PROFILE LOAD=default\n")

MACHINE = {
    "type": "machine",
    "name": PRINTER,
    "inherits": "MyKlipper 0.4 nozzle",
    "from": "User",
    "is_custom_defined": "0",
    "version": VER,
    "printer_settings_id": PRINTER,
    "printer_variant": "0.4",
    "printer_structure": "i3",
    "nozzle_diameter": ["0.4"],
    "nozzle_type": "brass",
    "extruder_type": ["Direct Drive"],
    "printer_extruder_id": ["1"],
    "printer_extruder_variant": ["Direct Drive Standard"],

    # Volumen real segun printer.cfg (position_max X250 / Y235 / Z270)
    "printable_area": ["0x0", "250x0", "250x235", "0x235"],
    "printable_height": "270",
    "bed_exclude_area": ["0x0"],
    "max_layer_height": ["0.32"],
    "min_layer_height": ["0.08"],

    # Firmware
    "use_relative_e_distances": "1",
    "use_firmware_retraction": "0",
    "emit_machine_limits_to_gcode": "0",
    "silent_mode": "0",
    "scan_first_layer": "0",
    "auxiliary_fan": "0",

    # Limites espejados de printer.cfg (solo estimacion de tiempo)
    "machine_max_speed_x": ["300", "300"],
    "machine_max_speed_y": ["300", "300"],
    "machine_max_speed_z": ["5", "5"],
    "machine_max_speed_e": ["50", "50"],
    "machine_max_acceleration_x": ["2000", "2000"],
    "machine_max_acceleration_y": ["2000", "2000"],
    "machine_max_acceleration_z": ["100", "100"],
    "machine_max_acceleration_e": ["2000", "2000"],
    "machine_max_acceleration_extruding": ["2000", "2000"],
    "machine_max_acceleration_retracting": ["2000", "2000"],
    "machine_max_acceleration_travel": ["2000", "2000"],
    "machine_max_jerk_x": ["5", "5"],
    "machine_max_jerk_y": ["5", "5"],
    "machine_max_jerk_z": ["0.4", "0.4"],
    "machine_max_jerk_e": ["2.5", "2.5"],
    "machine_min_extruding_rate": ["0", "0"],
    "machine_min_travel_rate": ["0", "0"],

    # Retraccion: Sprite Pro direct drive
    "retraction_length": ["0.6"],
    "retract_length_toolchange": ["1"],
    "retraction_speed": ["35"],
    "deretraction_speed": ["30"],
    "retraction_minimum_travel": ["1"],
    "retract_before_wipe": ["0%"],
    "retract_restart_extra": ["0"],
    "retract_restart_extra_toolchange": ["0"],
    "retract_when_changing_layer": ["1"],
    "wipe": ["1"],
    "wipe_distance": ["1"],
    "z_hop": ["0.2"],
    "z_hop_types": ["Auto Lift"],

    # Previews en Mainsail / Fluidd
    "thumbnails": ["32x32", "300x300"],
    "thumbnails_format": "PNG",

    # G-code. G92 E0 es obligatorio con extrusion relativa
    # (use_relative_e_distances=1): resetea el acumulador de E en cada capa y
    # evita perdida de precision en float. Orca rechaza el perfil si falta.
    "machine_start_gcode": START,
    "machine_end_gcode": "END_PRINT\n",
    "before_layer_change_gcode": ";BEFORE_LAYER_CHANGE\n;[layer_z]\n",
    "layer_change_gcode": ";AFTER_LAYER_CHANGE\n;[layer_z]\nG92 E0\n",
    "machine_pause_gcode": "PAUSE",
    "change_filament_gcode": "PAUSE",
    "time_lapse_gcode": "",

    # Defaults
    "default_print_profile": "0.20mm Standard " + SUF,
    "default_filament_profile": ["Printalot PLA " + SUF],

    # Host. Moonraker implementa la API de OctoPrint via [octoprint_compat],
    # por eso host_type es octoprint y no hay un tipo "moonraker" en Orca.
    "print_host": PLACEHOLDER_HOST,
    "print_host_webui": PLACEHOLDER_HOST,
    "host_type": "octoprint",

    "extruder_clearance_radius": "47",
    "extruder_clearance_height_to_rod": "34",
    "extruder_clearance_height_to_lid": "34",
}


# ============================================================================
# PROCESOS
# ============================================================================
# Techo de aceleracion 2000 mm/s2 = Klipper [printer] max_accel.
# Sin input shaper la pared exterior va a 1000 mm/s2 y velocidad baja.
COMMON = {
    "type": "process",
    "from": "User",
    "is_custom_defined": "0",
    "version": VER,
    "compatible_printers": COMPAT,

    "initial_layer_print_height": "0.2",
    "adaptive_layer_height": "0",

    # Aceleraciones
    "default_acceleration": "2000",
    "outer_wall_acceleration": "1000",
    "inner_wall_acceleration": "2000",
    "internal_solid_infill_acceleration": "2000",
    "sparse_infill_acceleration": "100%",
    "top_surface_acceleration": "1000",
    "bridge_acceleration": "50%",
    "initial_layer_acceleration": "500",
    "travel_acceleration": "2000",
    "initial_layer_travel_acceleration": ["1000"],
    # 0 = Orca no toca el square corner velocity, lo maneja Klipper (default 5)
    "default_jerk": "0",

    # Velocidades comunes
    "travel_speed": "250",
    "travel_speed_z": ["5"],
    "initial_layer_travel_speed": "100",
    "small_perimeter_speed": ["50%"],
    "small_perimeter_threshold": ["0"],
    "enable_overhang_speed": ["1"],
    "overhang_speed_classic": "0",
    "overhang_totally_speed": ["10"],
    "support_speed": "80",
    "support_interface_speed": "60",

    # Paredes
    "wall_generator": "arachne",
    "precise_outer_wall": "1",
    "only_one_wall_top": "1",
    "only_one_wall_first_layer": "0",
    "detect_thin_wall": "0",
    "detect_overhang_wall": "1",
    "detect_narrow_internal_solid_infill": "1",
    "ensure_vertical_shell_thickness": "ensure_moderate",
    "seam_position": "aligned",
    "staggered_inner_seams": "1",
    "seam_gap": "10%",
    "seam_slope_type": "none",
    "wipe_speed": "80%",
    "role_based_wipe_speed": "1",

    # Relleno
    "infill_wall_overlap": "15%",
    "top_bottom_infill_wall_overlap": "15%",
    "infill_direction": "45",
    "minimum_sparse_infill_area": "15",
    "gap_fill_target": "everywhere",
    "filter_out_gap_fill": "0.4",
    "internal_solid_infill_pattern": "monotonicline",
    "top_surface_pattern": "monotonicline",
    "bottom_surface_pattern": "monotonic",
    "is_infill_first": "0",
    "reduce_infill_retraction": "1",

    # Puentes y voladizos
    "bridge_flow": "0.95",
    "thick_bridges": "0",
    "slowdown_for_curled_perimeters": "1",

    # Compensaciones
    "elefant_foot_compensation": "0.15",
    "xy_hole_compensation": "0",
    "xy_contour_compensation": "0",

    # Adherencia. skirt_loops=0 porque START_PRINT ya purga con dos lineas
    "brim_type": "auto_brim",
    "brim_width": "5",
    "brim_object_gap": "0.1",
    "skirt_loops": "0",
    "draft_shield": "disabled",

    # Soportes
    "enable_support": "0",
    "support_type": "normal(auto)",
    "support_style": "default",
    "support_threshold_angle": "30",
    "support_top_z_distance": "0.2",
    "support_bottom_z_distance": "0.2",
    "support_object_xy_distance": "0.35",
    "support_base_pattern": "rectilinear",
    "support_base_pattern_spacing": "2.5",
    "support_interface_top_layers": "2",
    "support_interface_bottom_layers": "2",
    "support_interface_spacing": "0.2",
    "support_line_width": "0.36",
    "support_on_build_plate_only": "0",
    "support_remove_small_overhang": "1",

    # Salida. arc_fitting y exclude_object aprovechan [gcode_arcs] y
    # [exclude_object], que estan presentes en printer.cfg
    "resolution": "0.012",
    "enable_arc_fitting": "1",
    "exclude_object": "1",
    "gcode_label_objects": "1",
    "enable_prime_tower": "0",
    "timelapse_type": "0",
    "print_sequence": "by layer",
    "reduce_crossing_wall": "0",
    "max_travel_detour_distance": "0",
    "infill_combination": "0",
}


def _proc(name, inherits, extra):
    d = dict(COMMON)
    d["name"] = name
    d["inherits"] = inherits
    d["print_settings_id"] = name
    d.update(extra)
    return d


# 0.12mm Fine: detalle. Limitado por aceleracion, no por caudal.
FINE = _proc("0.12mm Fine " + SUF, "0.12mm Fine @MyKlipper", {
    "layer_height": "0.12",
    "line_width": "0.42",
    "initial_layer_line_width": "0.5",
    "outer_wall_line_width": "0.42",
    "inner_wall_line_width": "0.45",
    "top_surface_line_width": "0.4",
    "internal_solid_infill_line_width": "0.42",
    "sparse_infill_line_width": "0.45",
    "outer_wall_speed": "55",
    "inner_wall_speed": "120",
    "sparse_infill_speed": "140",
    "internal_solid_infill_speed": "130",
    "top_surface_speed": "40",
    "gap_infill_speed": "40",
    "internal_bridge_speed": "70",
    "bridge_speed": "35",
    "initial_layer_speed": "25",
    "initial_layer_infill_speed": "55",
    "overhang_1_4_speed": "0",
    "overhang_2_4_speed": "40",
    "overhang_3_4_speed": "22",
    "overhang_4_4_speed": "10",
    # a 0.12 de capa el ringing se nota mas: 800 en vez de 1000
    "outer_wall_acceleration": "800",
    "top_surface_acceleration": "800",
    "wall_loops": "2",
    "top_shell_layers": "7",
    "top_shell_thickness": "0.84",
    "bottom_shell_layers": "5",
    "bottom_shell_thickness": "0.6",
    "sparse_infill_density": "15%",
    "sparse_infill_pattern": "grid",
    "reduce_crossing_wall": "1",
})

# 0.20mm Standard: el de todos los dias (DEFAULT)
STANDARD = _proc("0.20mm Standard " + SUF, "0.20mm Standard @MyKlipper", {
    "layer_height": "0.2",
    "line_width": "0.42",
    "initial_layer_line_width": "0.5",
    "outer_wall_line_width": "0.42",
    "inner_wall_line_width": "0.45",
    "top_surface_line_width": "0.4",
    "internal_solid_infill_line_width": "0.42",
    "sparse_infill_line_width": "0.45",
    "outer_wall_speed": "60",
    "inner_wall_speed": "110",
    # 120 mm/s x 0.45 x 0.20 = 10.8 mm3/s, justo debajo del tope de 11 del PLA:
    # asi el perfil corre a la velocidad nominal sin que Orca lo frene solo.
    "sparse_infill_speed": "120",
    "internal_solid_infill_speed": "120",
    "top_surface_speed": "45",
    "gap_infill_speed": "45",
    "internal_bridge_speed": "80",
    "bridge_speed": "40",
    "initial_layer_speed": "25",
    "initial_layer_infill_speed": "60",
    "overhang_1_4_speed": "0",
    "overhang_2_4_speed": "45",
    "overhang_3_4_speed": "25",
    "overhang_4_4_speed": "12",
    "wall_loops": "2",
    "top_shell_layers": "4",
    "top_shell_thickness": "0.8",
    "bottom_shell_layers": "3",
    "bottom_shell_thickness": "0.6",
    "sparse_infill_density": "15%",
    "sparse_infill_pattern": "grid",
})

# 0.20mm Strong: piezas funcionales. cubic en vez de grid porque a densidad alta
# el grid cruza la boquilla consigo misma y deja blobs.
STRONG = _proc("0.20mm Strong " + SUF, "0.20mm Standard @MyKlipper", {
    "layer_height": "0.2",
    "line_width": "0.44",
    "initial_layer_line_width": "0.5",
    "outer_wall_line_width": "0.42",
    "inner_wall_line_width": "0.45",
    "top_surface_line_width": "0.4",
    "internal_solid_infill_line_width": "0.44",
    "sparse_infill_line_width": "0.45",
    "outer_wall_speed": "55",
    "inner_wall_speed": "100",
    "sparse_infill_speed": "110",
    "internal_solid_infill_speed": "110",
    "top_surface_speed": "45",
    "gap_infill_speed": "45",
    "internal_bridge_speed": "70",
    "bridge_speed": "40",
    "initial_layer_speed": "25",
    "initial_layer_infill_speed": "55",
    "overhang_1_4_speed": "0",
    "overhang_2_4_speed": "45",
    "overhang_3_4_speed": "25",
    "overhang_4_4_speed": "12",
    "wall_loops": "4",
    "top_shell_layers": "5",
    "top_shell_thickness": "1",
    "bottom_shell_layers": "4",
    "bottom_shell_thickness": "0.8",
    "sparse_infill_density": "40%",
    "sparse_infill_pattern": "cubic",
    "ensure_vertical_shell_thickness": "ensure_all",
    "infill_wall_overlap": "25%",
    "alternate_extra_wall": "0",
})

# 0.28mm Draft: prototipos y piezas grandes. Limitado por caudal, no por
# velocidad: a 0.28 de capa cada mm de recorrido mueve mucho mas plastico.
DRAFT = _proc("0.28mm Draft " + SUF, "0.28mm Extra Draft @MyKlipper", {
    "layer_height": "0.28",
    "initial_layer_print_height": "0.25",
    "line_width": "0.45",
    "initial_layer_line_width": "0.5",
    "outer_wall_line_width": "0.42",
    "inner_wall_line_width": "0.48",
    "top_surface_line_width": "0.42",
    "internal_solid_infill_line_width": "0.45",
    "sparse_infill_line_width": "0.5",
    "outer_wall_speed": "50",
    "inner_wall_speed": "80",
    "sparse_infill_speed": "75",
    "internal_solid_infill_speed": "80",
    "top_surface_speed": "45",
    "gap_infill_speed": "40",
    "internal_bridge_speed": "60",
    "bridge_speed": "35",
    "initial_layer_speed": "25",
    "initial_layer_infill_speed": "55",
    "overhang_1_4_speed": "0",
    "overhang_2_4_speed": "40",
    "overhang_3_4_speed": "22",
    "overhang_4_4_speed": "10",
    "wall_loops": "2",
    "top_shell_layers": "3",
    "top_shell_thickness": "0.84",
    "bottom_shell_layers": "2",
    "bottom_shell_thickness": "0.56",
    "sparse_infill_density": "10%",
    "sparse_infill_pattern": "grid",
    "infill_combination": "1",
})

PROCESSES = [FINE, STANDARD, STRONG, DRAFT]


# ============================================================================
# FILAMENTOS
# ============================================================================
def _plates(t, first):
    """Todas las variantes de placa con la misma temperatura: el perfil funciona
    sin importar que 'Bed type' este seleccionado en la UI."""
    out = {}
    for k in ("cool_plate", "eng_plate", "hot_plate", "textured_plate",
              "textured_cool_plate", "supertack_plate"):
        out[k + "_temp"] = [str(t)]
        out[k + "_temp_initial_layer"] = [str(first)]
    return out


def _fil(name, inherits, ftype, extra):
    d = {
        "type": "filament",
        "name": name,
        "inherits": inherits,
        "from": "User",
        "is_custom_defined": "0",
        "version": VER,
        "filament_settings_id": [name],
        "filament_vendor": ["Printalot"],
        "filament_type": [ftype],
        "filament_diameter": ["1.75"],
        "filament_extruder_variant": ["Direct Drive Standard"],
        "compatible_printers": COMPAT,
        "slow_down_for_layer_cooling": ["1"],
        "reduce_fan_stop_start_freq": ["1"],
        "enable_overhang_bridge_fan": ["1"],
        # pressure_advance queda pre-cargado pero DESACTIVADO: activarlo emite
        # SET_PRESSURE_ADVANCE sin tocar printer.cfg, pero conviene calibrar
        # primero con Calibration -> Pressure Advance.
        "enable_pressure_advance": ["0"],
    }
    d.update(extra)
    return d


PLA = _fil("Printalot PLA " + SUF, "Generic PLA @System", "PLA", dict(
    _plates(60, 60),
    filament_density=["1.24"], filament_cost=["25"],
    filament_flow_ratio=["0.98"], filament_max_volumetric_speed=["11"],
    nozzle_temperature=["210"], nozzle_temperature_initial_layer=["215"],
    nozzle_temperature_range_low=["190"], nozzle_temperature_range_high=["230"],
    temperature_vitrification=["55"],
    close_fan_the_first_x_layers=["1"], full_fan_speed_layer=["3"],
    fan_min_speed=["100"], fan_max_speed=["100"], fan_cooling_layer_time=["45"],
    overhang_fan_speed=["100"], overhang_fan_threshold=["25%"],
    slow_down_layer_time=["6"], slow_down_min_speed=["20"],
    pressure_advance=["0.04"],
    filament_notes=["Printalot PLA - 1.75mm\n"
                    "Perfil para Ender 3 S1 Pro + Klipper, nozzle 0.4.\n"
                    "Caudal maximo 11 mm3/s (hotend bimetalico stock).\n"
                    "Chapa PEI lado LISO: 60 grados alcanza. Limpiar con alcohol isopropilico.\n"
                    "Pressure advance sugerido 0.04 (desactivado hasta calibrar)."],
))

PETG = _fil("Printalot PETG " + SUF, "Generic PETG @System", "PETG", dict(
    _plates(70, 70),
    filament_density=["1.27"], filament_cost=["30"],
    filament_flow_ratio=["0.95"], filament_max_volumetric_speed=["9"],
    nozzle_temperature=["240"], nozzle_temperature_initial_layer=["245"],
    nozzle_temperature_range_low=["220"], nozzle_temperature_range_high=["260"],
    temperature_vitrification=["80"],
    close_fan_the_first_x_layers=["2"], full_fan_speed_layer=["4"],
    fan_min_speed=["40"], fan_max_speed=["60"], fan_cooling_layer_time=["25"],
    overhang_fan_speed=["70"], overhang_fan_threshold=["25%"],
    slow_down_layer_time=["8"], slow_down_min_speed=["20"],
    filament_retraction_length=["0.8"], filament_retraction_speed=["30"],
    filament_deretraction_speed=["25"], filament_retract_before_wipe=["0%"],
    filament_wipe=["1"],
    pressure_advance=["0.06"],
    filament_notes=["Printalot PETG - 1.75mm\n"
                    "OJO con la chapa PEI del lado LISO: el PETG se suelda al PEI y arranca\n"
                    "pedazos de la lamina. Usar SIEMPRE stick de pegamento como separador\n"
                    "y despegar recien con la cama fria.\n"
                    "Cama a 70, no subir mas. Primera capa menos aplastada que en PLA.\n"
                    "Caudal maximo 9 mm3/s. Pressure advance sugerido 0.06."],
))

ABS = _fil("Printalot ABS " + SUF, "Generic ABS @System", "ABS", dict(
    _plates(100, 100),
    filament_density=["1.04"], filament_cost=["30"],
    filament_flow_ratio=["0.98"], filament_max_volumetric_speed=["10"],
    nozzle_temperature=["245"], nozzle_temperature_initial_layer=["250"],
    nozzle_temperature_range_low=["230"], nozzle_temperature_range_high=["270"],
    temperature_vitrification=["100"], filament_shrink=["100.6%"],
    close_fan_the_first_x_layers=["3"], full_fan_speed_layer=["0"],
    fan_min_speed=["0"], fan_max_speed=["15"], fan_cooling_layer_time=["20"],
    overhang_fan_speed=["25"], overhang_fan_threshold=["25%"],
    slow_down_layer_time=["15"], slow_down_min_speed=["20"],
    filament_retraction_length=["0.6"], filament_retraction_speed=["35"],
    activate_air_filtration=["0"],
    pressure_advance=["0.05"],
    filament_notes=["Printalot ABS - 1.75mm. IMPRESORA SIN ENCERRAMIENTO\n"
                    "Ventilador practicamente apagado (0-15%) para evitar delaminado.\n"
                    "Obligatorio en el proceso: Brim tipo outer_only con 8mm de ancho.\n"
                    "Recomendado: Draft shield = enabled en piezas altas o finas.\n"
                    "Cerrar puertas y ventanas del ambiente, cero corriente de aire.\n"
                    "Piezas mayores a ~100mm van a warpear igual sin caja.\n"
                    "Compensacion de contraccion 100.6%. El ABS emite VOC: ventilar despues."],
))

TPU = _fil("Printalot TPU Flex " + SUF, "Generic TPU @System", "TPU", dict(
    _plates(45, 45),
    filament_density=["1.21"], filament_cost=["45"],
    filament_flow_ratio=["1"], filament_max_volumetric_speed=["3.5"],
    nozzle_temperature=["230"], nozzle_temperature_initial_layer=["230"],
    nozzle_temperature_range_low=["210"], nozzle_temperature_range_high=["240"],
    temperature_vitrification=["60"],
    close_fan_the_first_x_layers=["1"], full_fan_speed_layer=["2"],
    fan_min_speed=["50"], fan_max_speed=["80"], fan_cooling_layer_time=["20"],
    overhang_fan_speed=["80"], overhang_fan_threshold=["25%"],
    slow_down_layer_time=["6"], slow_down_min_speed=["10"],
    filament_retraction_length=["0.4"], filament_retraction_speed=["20"],
    filament_deretraction_speed=["20"], filament_retraction_minimum_travel=["3"],
    filament_retract_when_changing_layer=["0"], filament_z_hop=["0"],
    filament_wipe=["0"], filament_retract_before_wipe=["0%"],
    pressure_advance=["0.6"],
    filament_notes=["Printalot Flex / TPU (shore ~95A) - 1.75mm\n"
                    "El caudal maximo de 3.5 mm3/s es el que manda: Orca frena todas las\n"
                    "velocidades solo. No hace falta un proceso distinto.\n"
                    "Retraccion minima (0.4mm) y sin z-hop para que no se trabe el Sprite.\n"
                    "Cargar el filamento a mano, despacio, con el extrusor caliente.\n"
                    "Pressure advance sugerido 0.6 (el TPU necesita valores altos)."],
))

FILAMENTS = [PLA, PETG, ABS, TPU]


# ============================================================================
# API
# ============================================================================
# Seleccion que queda activa al abrir OrcaSlicer
DEFAULT_PROCESS = STANDARD["name"]
DEFAULT_FILAMENT = PLA["name"]
# curr_bed_type 3 = High Temp Plate = chapa PEI del lado liso
DEFAULT_BED_TYPE = "3"
# Filamentos de sistema que quedan visibles: solo los padres de los Printalot
KEEP_SYSTEM_FILAMENTS = [f["inherits"] for f in FILAMENTS]


def all_presets():
    """[(kind, name, config, base_id)] para los 9 perfiles."""
    out = [("machine", MACHINE["name"], MACHINE, BASE_IDS[MACHINE["inherits"]])]
    for p in PROCESSES:
        out.append(("process", p["name"], p, BASE_IDS[p["inherits"]]))
    for f in FILAMENTS:
        out.append(("filament", f["name"], f, BASE_IDS[f["inherits"]]))
    return out
