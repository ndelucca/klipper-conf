"""Definición de los perfiles de OrcaSlicer para Ender 3 S1 Pro + Klipper.

Este archivo es la FUENTE DE VERDAD de toda la configuración. No escribe nada:
solo construye las estructuras. `orca.py build` las vuelca a presets/ y
`orca.py install` las copia al directorio de datos de OrcaSlicer.

Para cambiar algo de forma permanente: editar acá, correr `orca.py build`, y
commitear el cambio junto con el snapshot regenerado.

Contexto de hardware (leído de printer.cfg vía Moonraker, 2026-08-26):

    Cinemática     cartesian (bed slinger)
    Área util      X 220 x Y 220 (chapa) - el carro llega a 250 x 235
    Altura util    Z 270 mm
    Extrusor       Sprite Pro direct drive, gear ratio 42:12
    Hotend         bimetálico, max_temp 300
    Cama           max_temp 110
    max_velocity   300 mm/s
    max_accel      2000 mm/s2   <- techo real de todas las aceleraciones
    max_z_velocity  10 mm/s
    [input_shaper]     NO CONFIGURADO
    pressure_advance   NO CONFIGURADO
"""

from dataclasses import replace
from typing import NamedTuple

from orcakit.presets import Filament, Machine, Preset, Process

PRINTER = "EnderS1ProKlipper"
SUF = "@EnderS1Pro"
COMPAT = (PRINTER,)

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
# Contrato con el macro START_PRINT de versions/<CURRENT>/macros.cfg.
# `orca.py check` valida que los parámetros que se pasan acá sean exactamente
# los que la macro lee de params.
#
# MATERIAL es lo que hace que Klipper pueda poner el pressure advance por su
# cuenta: la macro tiene la tabla por material y el laminador solo anuncia cuál
# está cargado. Así cualquier gcode hereda el PA correcto, venga de donde venga.
#
# La carga de la malla ya NO está acá: la hace START_PRINT, porque la malla es
# de la máquina y no del laminador.
# LAYER existe porque la linea de purga del macro se imprimia a un 0.28 fijo
# mientras los procesos imprimen a 0.20 (0.25 en Draft). Esa linea existe para
# juzgar la primera capa, y a 0.28 salia redondeada aunque el z_offset
# estuviera 0.05 alto: daba una lectura optimista justo de lo que sirve para
# diagnosticar.
#
# SOAK ya NO se manda desde aca, y esa ausencia es la decision.
#
# Es el tiempo que START_PRINT espera despues de que M190 vuelve, antes del
# re-home en caliente: M190 vuelve cuando el TERMISTOR toca el target, y ese
# termistor esta pegado abajo de la chapa, asi que sin la espera la referencia
# de Z se toma sobre una cama a mitad de camino y despues se carga una malla
# que si se midio en equilibrio.
#
# Estuvo clavado en SOAK=90 mientras el macro elegia la malla solo, por
# BED_TEMP. Eran dos respuestas a una sola pregunta -que regimen termico es
# este- y la que estaba clavada era la equivocada: el ABS hacia 90 s de soak y
# despues cargaba la malla medida en equilibrio a 100 grados.
#
# Ahora la escalera vive una sola vez, en el macro, junto a la que elige la
# malla. El macro sigue leyendo SOAK= como override, asi que se puede volver a
# mandar desde aca para un caso puntual; `check` sabe que es opcional porque lo
# lee con un |default(...).
# EL PREAMBULO DE DOS LINEAS NO ES DECORACION, Y NO FIJA NADA.
#
# OrcaSlicer decide si emitir SUS PROPIOS comandos de temperatura buscando
# M104/M109 y M140/M190 LITERALES en este texto. Sin ellos los inserta por
# delante de la llamada al macro, y ahi se caen tres cosas de golpe:
#
#   - el pre-flight de filamento de START_PRINT deja de correr "antes de
#     encender nada": aborta con la cama ya en target y el nozzle tambien, y
#     action_raise_error no los apaga.
#   - el `M104 S150` del macro deja de ser un precalentamiento en paralelo y
#     pasa a ser un ENFRIAMIENTO desde el target que puso el laminador. El
#     nozzle hace 25 -> 220 -> 150 -> 220.
#   - nada de eso falla. El soak es tiempo de reloj, la malla se carga igual y
#     la pieza sale bien, asi que no hay sintoma que delate el problema.
#
# Las dos lineas de abajo son exactamente lo que el macro va a volver a hacer
# tres lineas despues, asi que no le sacan la decision a nadie: existen para
# que el laminador VEA que ya estan y no ponga las suyas. `orca.py check`
# valida que sigan ahi, porque borrarlas no rompe nada visible.
START = ("M140 S[bed_temperature_initial_layer_single]\n"
         "M104 S150\n"
         "START_PRINT BED_TEMP=[bed_temperature_initial_layer_single] "
         "EXTRUDER_TEMP=[nozzle_temperature_initial_layer] "
         "MATERIAL=[filament_type] "
         "LAYER=[initial_layer_print_height]\n")

MACHINE = Machine(
    name=PRINTER,
    inherits="MyKlipper 0.4 nozzle",
    printer_variant="0.4",
    printer_structure="i3",
    nozzle_diameter=("0.4",),
    nozzle_type="brass",
    extruder_type=("Direct Drive",),
    printer_extruder_id=("1",),
    printer_extruder_variant=("Direct Drive Standard",),

    # Area util de la CHAPA, que no es lo mismo que el recorrido del carro.
    # [stepper_x] position_max 250 / [stepper_y] 235 es hasta donde llega el
    # carro; el plato magnetico de la S1 Pro es 235x235 con 220x220 utiles.
    # Declarar 250x235 aca dejaba a Orca poner una pieza 30 mm fuera del plato.
    # check valida que esto ENTRE en el recorrido, no que sea igual.
    #
    # La malla llega solo hasta X=200 ([bed_mesh] mesh_max, limite fisico del
    # x_offset -48 del BLTouch), asi que de X=200 a 220 el Z esta extrapolado.
    printable_area=("0x0", "220x0", "220x220", "0x220"),
    printable_height="270",
    # Vacio, no ("0x0",). Estuvo con un poligono de UN punto, que no excluye
    # nada pero tampoco significa nada: es un valor que aparenta declarar una
    # zona prohibida y no declara ninguna.
    bed_exclude_area=(),
    max_layer_height=("0.32",),
    min_layer_height=("0.08",),

    # Firmware
    use_relative_e_distances="1",
    use_firmware_retraction="0",
    emit_machine_limits_to_gcode="0",
    silent_mode="0",
    scan_first_layer="0",
    auxiliary_fan="0",

    # Limites espejados de printer.cfg (solo estimacion de tiempo).
    # Las aceleraciones son el TECHO MECANICO de la maquina ([printer]
    # max_accel = 3000), no el presupuesto de ringing: ese vive en las
    # aceleraciones por feature de cada proceso, mas abajo. check compara
    # estas contra max_accel, y aquellas contra el techo de ringing.
    machine_max_speed_x=("300", "300"),
    machine_max_speed_y=("300", "300"),
    machine_max_speed_z=("10", "10"),
    machine_max_speed_e=("50", "50"),
    machine_max_acceleration_x=("3000", "3000"),
    machine_max_acceleration_y=("3000", "3000"),
    machine_max_acceleration_z=("200", "200"),
    machine_max_acceleration_e=("3000", "3000"),
    machine_max_acceleration_extruding=("3000", "3000"),
    machine_max_acceleration_retracting=("3000", "3000"),
    machine_max_acceleration_travel=("3000", "3000"),
    machine_max_jerk_x=("5", "5"),
    machine_max_jerk_y=("5", "5"),
    machine_max_jerk_z=("0.4", "0.4"),
    machine_max_jerk_e=("2.5", "2.5"),
    machine_min_extruding_rate=("0", "0"),
    machine_min_travel_rate=("0", "0"),

    # Retraccion: Sprite Pro direct drive
    retraction_length=("0.6",),
    retract_length_toolchange=("1",),
    retraction_speed=("35",),
    deretraction_speed=("30",),
    # 2 mm y no 1. Con 1 mm el Sprite retraia en practicamente cada travel:
    # cada par retraccion/reposicion mete un transitorio de presion, y aunque
    # wipe=1 y reduce_infill_retraction=1 lo tapan casi siempre, son cientos
    # de oportunidades por capa de que no lo tapen.
    retraction_minimum_travel=("2",),
    retract_before_wipe=("0%",),
    retract_restart_extra=("0",),
    retract_restart_extra_toolchange=("0",),
    retract_when_changing_layer=("1",),
    wipe=("1",),
    wipe_distance=("1",),
    # 0.3 y no 0.2. Auto Lift solo levanta al pasar por encima de lo ya
    # impreso, y 0.2 mm es menos despeje que un blob o que un borde levantado
    # -y slowdown_for_curled_perimeters esta en 1, o sea que el perfil ya
    # asume que hay perimetros que se curvan-. Con max_z_velocity en 10 mm/s
    # el costo en tiempo es despreciable, y el modo de falla que evita
    # -enganchar la pieza y despegarla- se lleva la impresion entera.
    z_hop=("0.3",),
    z_hop_types=("Auto Lift",),

    # Previews en Mainsail / Fluidd
    thumbnails=("32x32", "300x300"),
    thumbnails_format="PNG",

    # G-code. G92 E0 es obligatorio con extrusion relativa
    # (use_relative_e_distances=1): resetea el acumulador de E en cada capa y
    # evita perdida de precision en float. Orca rechaza el perfil si falta.
    machine_start_gcode=START,
    machine_end_gcode="END_PRINT\n",
    before_layer_change_gcode=";BEFORE_LAYER_CHANGE\n;[layer_z]\n",
    layer_change_gcode=";AFTER_LAYER_CHANGE\n;[layer_z]\nG92 E0\n",
    machine_pause_gcode="PAUSE",
    change_filament_gcode="PAUSE",
    time_lapse_gcode="",

    # Defaults
    default_print_profile="0.20mm Standard " + SUF,
    default_filament_profile=("Printalot PLA " + SUF,),

    # Host. Moonraker implementa la API de OctoPrint via [octoprint_compat],
    # por eso host_type es octoprint y no hay un tipo "moonraker" en Orca.
    print_host=PLACEHOLDER_HOST,
    print_host_webui=PLACEHOLDER_HOST,
    host_type="octoprint",

    extruder_clearance_radius="47",
    extruder_clearance_height_to_rod="34",
    extruder_clearance_height_to_lid="34",
)


# ============================================================================
# PROCESOS
# ============================================================================
# Techo de aceleracion 2000 mm/s2 = Klipper [printer] max_accel.
# Sin input shaper la pared exterior va a 1000 mm/s2 y velocidad baja.
COMMON = Process(
    compatible_printers=COMPAT,

    initial_layer_print_height="0.2",
    adaptive_layer_height="0",

    # Aceleraciones. Sin input shaper, la amplitud del ringing la manda la
    # aceleracion (no la velocidad), asi que las superficies que se ven van
    # bajas y el resto se queda en el techo de 2000.
    default_acceleration="2000",
    outer_wall_acceleration="700",
    inner_wall_acceleration="2000",
    internal_solid_infill_acceleration="2000",
    sparse_infill_acceleration="100%",
    top_surface_acceleration="700",
    bridge_acceleration="50%",
    initial_layer_acceleration="500",
    # 3000: el techo de [printer] max_accel, no el de ringing. Un
    # desplazamiento por el aire no toca la pieza, asi que no tiene por que
    # pagar el presupuesto de calidad superficial. Con 2000 llegar a los 250
    # de travel_speed exigia 15.6 mm y casi ningun travel real es tan largo;
    # con 3000 son 10.4 mm. Ver el comentario de max_accel en limits.cfg.
    travel_acceleration="3000",
    initial_layer_travel_acceleration=("1000",),
    # 0 = Orca no toca el square corner velocity, lo maneja Klipper (default 5)
    default_jerk="0",

    # Velocidades comunes
    travel_speed="250",
    travel_speed_z=("10",),
    initial_layer_travel_speed="100",
    # 40% del contorno exterior. Un agujero chico es un perimetro corto: sin
    # pressure advance calibrado, cuanto mas lento, mas pareja la extrusion.
    small_perimeter_speed=("40%",),
    small_perimeter_threshold=("0",),
    enable_overhang_speed=("1",),
    overhang_speed_classic="0",
    overhang_totally_speed=("10",),
    support_speed="80",
    support_interface_speed="60",

    # Paredes
    wall_generator="arachne",
    precise_outer_wall="1",
    only_one_wall_top="1",
    only_one_wall_first_layer="0",
    detect_thin_wall="0",
    detect_overhang_wall="1",
    detect_narrow_internal_solid_infill="1",
    ensure_vertical_shell_thickness="ensure_moderate",
    seam_position="aligned",
    staggered_inner_seams="1",
    seam_gap="10%",
    # Scarf joint apagado ACA a proposito: se activa por proceso, no en comun.
    # Reparte el solape de la costura en una rampa de varios milimetros en vez
    # de cortar y volver a arrancar en el mismo punto, que es lo que deja el
    # blob. Solo vale la pena en los perfiles que se miran de cerca: en Draft
    # es tiempo gastado en una superficie que a nadie le importa.
    seam_slope_type="none",
    wipe_speed="80%",
    role_based_wipe_speed="1",

    # Relleno
    infill_wall_overlap="15%",
    top_bottom_infill_wall_overlap="15%",
    infill_direction="45",
    minimum_sparse_infill_area="15",
    gap_fill_target="everywhere",
    filter_out_gap_fill="0.4",
    internal_solid_infill_pattern="monotonicline",
    top_surface_pattern="monotonicline",
    bottom_surface_pattern="monotonic",

    # Planchado apagado ACA a proposito, igual que el scarf joint: se prende
    # por proceso. Solo vale la pena donde la cara superior se mira; en Draft
    # y en Strong es tiempo gastado en una superficie que a nadie le importa.
    ironing_type="no ironing",

    # Patron del relleno disperso. El argumento habitual a favor de gyroid es
    # la isotropia, y al 10-15% de densidad eso importa poco. Lo que importa
    # aca es otra cosa: grid SE CRUZA CONSIGO MISMO dentro de la misma capa, y
    # en cada interseccion el nozzle pasa por encima de material ya extruido.
    # En una bed slinger sin input shaper cada uno de esos golpes excita la
    # resonancia justo cuando la aceleracion ya esta en el techo de 2000.
    # Gyroid no se cruza nunca: una sola trayectoria continua por capa.
    #
    # El costo esta en la Pi, no en la impresora: gyroid es todo curvas, y con
    # enable_arc_fitting=1 salen como G2/G3 que Klipper re-expande en segmentos
    # de 0.1 mm ([gcode_arcs] resolution en limits.cfg). A 110 mm/s eso es
    # ~1100 segmentos por segundo de trabajo para una 3B+. Si alguna vez el
    # relleno tartamudea, el primer lugar donde mirar es subir esa resolution,
    # no bajar la velocidad.
    #
    # Strong lo pisa con cubic: ver el comentario alla.
    sparse_infill_pattern="gyroid",
    is_infill_first="0",
    reduce_infill_retraction="1",

    # Puentes y voladizos.
    # overhang_reverse imprime el perimetro en voladizo en sentido inverso, de
    # modo que arranque anclado en material solido en vez de en el aire. Junto
    # con el perimetro extra es lo que endereza el techo de un agujero chico
    # impreso sin soportes.
    bridge_flow="0.95",
    thick_bridges="0",
    slowdown_for_curled_perimeters="1",
    overhang_reverse="1",
    overhang_reverse_threshold="50%",
    overhang_reverse_internal_only="0",
    extra_perimeters_on_overhangs="1",

    # Compensaciones. SIN MEDIR TODAVIA: los valores quedan como estaban a
    # proposito, porque una compensacion mal puesta se aplica a todos los
    # agujeros de todas las piezas e introduce un error sistematico en la
    # direccion contraria. Peor que no compensar.
    #
    # Pendiente: OrcaSlicer -> Calibration -> Tolerance. Imprime bloques con
    # agujeros de medida conocida, se miden con calibre, y sale
    #     xy_hole_compensation = (nominal - medido) / 2
    # Un agujero sale sistematicamente mas chico que el modelo porque el
    # perimetro interno es convexo hacia adentro y el plastico se contrae hacia
    # el centro del arco. En un nozzle 0.4 el error tipico es 0.05-0.15 mm de
    # diametro: en un agujero de 5 mm eso decide si entra un M5 o no.
    #
    # Ojo que esto es OTRA cosa que el agujero deformado que se arreglo con
    # overhang_reverse + extra_perimeters_on_overhangs: aquello era la FORMA,
    # esto es el TAMANO. Se pueden tener las dos mal por separado.
    #
    # elefant_foot_compensation 0.15 tambien es un valor generico heredado.
    # Depende del z_offset, de la temperatura de cama y del PEI concreto.
    # Sintoma de pasarse: la primera capa queda mas angosta que la segunda, con
    # escalon. Sintoma de quedarse corto: la pestana aplastada que sobresale.
    elefant_foot_compensation="0.15",
    xy_hole_compensation="0",
    xy_contour_compensation="0",

    # Adherencia. skirt_loops=0 porque START_PRINT ya purga con dos lineas
    brim_type="auto_brim",
    brim_width="5",
    brim_object_gap="0.1",
    skirt_loops="0",
    draft_shield="disabled",

    # Soportes
    enable_support="0",
    support_type="normal(auto)",
    support_style="default",
    support_threshold_angle="30",
    # support_top_z_distance y support_bottom_z_distance NO estan aca: son de
    # los pocos valores que dependen de la altura de capa y por lo tanto no
    # pueden ser comunes. Orca redondea el hueco al multiplo de layer_height
    # mas cercano, asi que un 0.2 unico daba 0.24 en Fine (0.12) y 0.28 en
    # Draft (0.28): tres huecos distintos donde el perfil declaraba uno.
    # El hueco tiene que ser UNA capa exacta de aire, que es el compromiso
    # entre que el soporte se despegue y que la superficie salga limpia.
    # `orca.py check` valida que sea multiplo entero de la altura de capa.
    support_object_xy_distance="0.35",
    support_base_pattern="rectilinear",
    support_base_pattern_spacing="2.5",
    support_interface_top_layers="2",
    support_interface_bottom_layers="2",
    support_interface_spacing="0.2",
    support_line_width="0.36",
    support_on_build_plate_only="0",
    support_remove_small_overhang="1",

    # Salida.
    # arc_fitting ACTIVADO. Depende de que [gcode_arcs] en limits.cfg declare
    # `resolution: 0.1`. Con el default de Klipper (1.0 mm) el arco llega entero
    # pero se parte en cuerdas de 1 mm, lo que en un radio de 2 mm deja 0.064 mm
    # de facetado visible; con 0.1 mm el error baja a 0.0006 mm y ademas el
    # gcode es mucho mas chico que emitiendo segmentos de 0.012 mm.
    # `orca.py check` valida ese par: si alguien sube la resolution de Klipper
    # por encima de 0.2, falla y hay que volver a poner esto en "0".
    resolution="0.012",
    enable_arc_fitting="1",
    exclude_object="1",
    gcode_label_objects="1",
    enable_prime_tower="0",
    timelapse_type="0",
    print_sequence="by layer",
    # El evitado de paredes se prende por proceso (Fine, Standard, Strong), no
    # aca: Draft existe para ir rapido y el rodeo es tiempo.
    #
    # Pero el LIMITE del rodeo si es comun, y tiene que estar puesto donde el
    # evitado se prenda. En Orca, max_travel_detour_distance = 0 NO significa
    # "sin rodeo": significa rodeo SIN LIMITE. O sea que Fine, que ya tenia
    # reduce_crossing_wall en 1, venia aceptando cualquier desvio con tal de no
    # cruzar un perimetro, incluyendo los patologicos. 50% acota el desvio a la
    # mitad del camino directo, que es donde deja de compensar: mas que eso es
    # mas oozing y mas tiempo que la cicatriz que estas evitando.
    reduce_crossing_wall="0",
    max_travel_detour_distance="50%",
    infill_combination="0",
)


# 0.12mm Fine: detalle. Limitado por aceleracion, no por caudal.
FINE = replace(
    COMMON,
    name="0.12mm Fine " + SUF,
    inherits="0.12mm Fine @MyKlipper",
    layer_height="0.12",
    line_width="0.42",
    initial_layer_line_width="0.5",
    outer_wall_line_width="0.42",
    inner_wall_line_width="0.45",
    top_surface_line_width="0.4",
    internal_solid_infill_line_width="0.42",
    sparse_infill_line_width="0.45",
    outer_wall_speed="45",
    inner_wall_speed="120",
    sparse_infill_speed="140",
    internal_solid_infill_speed="130",
    top_surface_speed="40",
    gap_infill_speed="40",
    internal_bridge_speed="70",
    bridge_speed="35",
    initial_layer_speed="25",
    initial_layer_infill_speed="55",
    overhang_1_4_speed="0",
    overhang_2_4_speed="35",
    overhang_3_4_speed="20",
    overhang_4_4_speed="10",
    # a 0.12 de capa el ringing se nota mas: 600 en vez de 700
    outer_wall_acceleration="600",
    top_surface_acceleration="600",
    wall_loops="2",
    top_shell_layers="7",
    top_shell_thickness="0.84",
    bottom_shell_layers="5",
    bottom_shell_thickness="0.6",
    sparse_infill_density="15%",
    reduce_crossing_wall="1",
    # Dos capas de 0.12. Una sola (0.12) no deja aire suficiente para separar
    # el soporte de la pieza; es el unico proceso donde el hueco no es una
    # capa, y es porque la capa es la mitad de fina que en el resto.
    support_top_z_distance="0.24",
    support_bottom_z_distance="0.24",
    # Planchado de la cara superior. Es la mitad que faltaba: monotonicline
    # ordena las pasadas y only_one_wall_top saca la costura del medio, pero
    # entre linea y linea sigue quedando el valle del propio cordon. El
    # planchado lo rellena pasando el nozzle casi vacio por encima.
    #
    # `top` y no `topmost`: plancha toda cara superior expuesta, no solo la
    # ultima capa del objeto. `all solid` tambien plancharia las solidas
    # internas, que nadie ve, y es tiempo tirado.
    #
    # flow 10% es material apenas suficiente para llenar los valles sin
    # acumular; spacing 0.15 es solape agresivo a proposito (el objetivo es
    # fundir, no depositar); speed 30 porque el planchado es sensible a la
    # inercia y va sobre la superficie que menos perdona.
    #
    # Cuesta tiempo SOLO en caras superiores: no toca el resto de la pieza.
    # El angulo si se corrige, igual que en Standard: sin declarar vale -1, o
    # sea el mismo que el relleno superior, y el nozzle plancha paralelo a los
    # cordones en vez de cruzarlos. Con infill_direction en 45, un 0 cruza a 45
    # grados. Eso no cuesta tiempo; el spacing y la velocidad si, y aca no se
    # tocan a proposito.
    ironing_type="top",
    ironing_flow="10%",
    ironing_speed="30",
    ironing_spacing="0.15",
    ironing_angle="0",
    # Scarf joint. `conditional` hace que se aplique solo donde la pared es lo
    # bastante lisa (angulo > 155 grados): en una esquina viva el scarf se ve
    # peor que la costura normal, asi que ahi se abstiene.
    seam_slope_type="external",
    seam_slope_conditional="1",
    scarf_angle_threshold="155",
)

# 0.20mm Standard: el de todos los dias (DEFAULT)
STANDARD = replace(
    COMMON,
    name="0.20mm Standard " + SUF,
    inherits="0.20mm Standard @MyKlipper",
    layer_height="0.2",
    line_width="0.42",
    initial_layer_line_width="0.5",
    outer_wall_line_width="0.42",
    inner_wall_line_width="0.45",
    top_surface_line_width="0.4",
    internal_solid_infill_line_width="0.42",
    sparse_infill_line_width="0.45",
    # La pared exterior es lo unico que se ve. Bajarla de 60 a 50 cuesta poco
    # tiempo (es una fraccion chica del total) y da extrusion mas pareja
    # mientras no haya pressure advance calibrado.
    outer_wall_speed="50",
    inner_wall_speed="110",
    # Standard es el unico proceso cuyo principio de diseno es NO tocar nunca el
    # techo de caudal del PLA: corre a la velocidad nominal y el auto-freno de
    # Orca queda de red para los otros materiales. Draft es lo contrario, y esta
    # documentado como tal: ahi el limite ES el caudal.
    #
    # Con el techo del PLA en 10 mm3/s, los nominales que respetan eso son:
    #    110 x 0.45 x 0.20 = 9.90   relleno disperso
    #    115 x 0.42 x 0.20 = 9.66   relleno solido
    #    110 x 0.45 x 0.20 = 9.90   pared interior
    #
    # Estaban en 120, calculados contra el techo viejo de 11. Con 10 la maquina
    # los ejecutaba igual a 111 y 119: el archivo decia una cosa y la impresora
    # hacia otra. Bajar el nominal no imprime mas lento, hace que el numero
    # escrito sea el numero que pasa. Cuando Max Flowrate de el techo real,
    # estos tres suben con el.
    sparse_infill_speed="110",
    internal_solid_infill_speed="115",
    top_surface_speed="45",
    gap_infill_speed="45",
    internal_bridge_speed="80",
    bridge_speed="40",
    initial_layer_speed="25",
    initial_layer_infill_speed="60",
    overhang_1_4_speed="0",
    overhang_2_4_speed="40",
    overhang_3_4_speed="22",
    overhang_4_4_speed="10",
    # TRES paredes y no dos. Dos es el default de la industria, y es una
    # eleccion de VELOCIDAD: con 2, la pared exterior se deposita contra el
    # relleno al 15%, o sea contra aire la mayor parte del recorrido. Con 3
    # queda apoyada contra material solido, que es lo que decide la precision
    # dimensional y el comportamiento en voladizo.
    #
    # Y es lo que habilita la linea de abajo: inner-outer-inner necesita 3
    # paredes o mas para significar algo. Con 2 degeneraba al orden normal, y
    # por eso hasta ahora vivia solo en Strong.
    #
    # Cuesta del orden de 15-20% de tiempo en piezas de pared fina. Es el
    # proceso de todos los dias y el criterio declarado es calidad primero.
    wall_loops="3",
    wall_sequence="inner-outer-inner wall",
    top_shell_layers="4",
    top_shell_thickness="0.8",
    bottom_shell_layers="3",
    bottom_shell_thickness="0.6",
    sparse_infill_density="15%",
    # Una capa de 0.2 de aire.
    support_top_z_distance="0.2",
    support_bottom_z_distance="0.2",
    # Cruce de paredes. Cada travel que atraviesa un perimetro exterior deja
    # una cicatriz o un punto en la unica superficie que se ve, y este es el
    # perfil de todos los dias con criterio de calidad primero: paga 3 paredes
    # e inner-outer-inner y despues ahorraba justo aca. Fine ya lo tenia.
    # El limite del rodeo esta en COMMON, y los dos van juntos.
    reduce_crossing_wall="1",
    # Planchado de la cara superior. Es la mitad que faltaba: monotonicline
    # ordena las pasadas y only_one_wall_top saca la costura del medio, pero
    # entre linea y linea sigue quedando el valle del propio cordon. El
    # planchado lo rellena pasando el nozzle casi vacio por encima.
    #
    # `top` y no `topmost`: plancha toda cara superior expuesta, no solo la
    # ultima capa del objeto. `all solid` tambien plancharia las solidas
    # internas, que nadie ve, y es tiempo tirado.
    #
    # EL ANGULO ES EL ARREGLO. Sin declarar vale -1, que en Orca significa "el
    # mismo que el relleno superior", o sea que el nozzle planchaba PARALELO a
    # los cordones, recorriendo sus propios valles en vez de cruzarlos. Es el
    # peor angulo posible para lo que el planchado hace. Con infill_direction
    # en 45, un 0 cruza a 45 grados.
    #
    # Y el costo estaba muy por encima de lo que decia el comentario viejo
    # ("cuesta tiempo SOLO en caras superiores", cierto pero suena barato):
    #
    #   cara superior de 100 x 100 mm     pasadas   tiempo
    #     spacing 0.15  speed 30            667     37 min   <- estaba asi
    #     spacing 0.20  speed 60            500      7 min
    #
    # 0.2 sigue siendo el doble de solape sobre una linea de 0.4, y 60 mm/s no
    # es temerario: el planchado casi no extruye, asi que no lo limita el
    # caudal sino el ringing, y top_surface_acceleration ya esta en 700.
    #
    # Fine se queda en 0.15 / 30: ese es el perfil de calidad a cualquier
    # precio, y ahi el tiempo no es el criterio.
    ironing_type="top",
    ironing_flow="10%",
    ironing_speed="60",
    ironing_spacing="0.2",
    ironing_angle="0",
    # Scarf joint. `conditional` hace que se aplique solo donde la pared es lo
    # bastante lisa (angulo > 155 grados): en una esquina viva el scarf se ve
    # peor que la costura normal, asi que ahi se abstiene.
    seam_slope_type="external",
    seam_slope_conditional="1",
    scarf_angle_threshold="155",
)

# 0.20mm Strong: piezas funcionales. cubic en vez de grid porque a densidad alta
# el grid cruza la boquilla consigo misma y deja blobs.
STRONG = replace(
    COMMON,
    name="0.20mm Strong " + SUF,
    inherits="0.20mm Standard @MyKlipper",
    layer_height="0.2",
    line_width="0.44",
    initial_layer_line_width="0.5",
    outer_wall_line_width="0.42",
    inner_wall_line_width="0.45",
    top_surface_line_width="0.4",
    internal_solid_infill_line_width="0.44",
    sparse_infill_line_width="0.45",
    outer_wall_speed="50",
    inner_wall_speed="100",
    sparse_infill_speed="110",
    internal_solid_infill_speed="110",
    top_surface_speed="45",
    gap_infill_speed="45",
    internal_bridge_speed="70",
    bridge_speed="40",
    initial_layer_speed="25",
    initial_layer_infill_speed="55",
    overhang_1_4_speed="0",
    overhang_2_4_speed="40",
    overhang_3_4_speed="22",
    overhang_4_4_speed="10",
    wall_loops="4",
    top_shell_layers="5",
    top_shell_thickness="1",
    bottom_shell_layers="4",
    bottom_shell_thickness="0.8",
    sparse_infill_density="40%",
    # Una capa de 0.2 de aire.
    support_top_z_distance="0.2",
    support_bottom_z_distance="0.2",
    # Se aparta del gyroid de COMMON a proposito. Al 40% gyroid se vuelve
    # denso y lento sin dar nada a cambio: su ventaja es la continuidad de la
    # trayectoria, que a esa densidad ya no se nota. Cubic apila celdas en las
    # tres dimensiones, que es lo que se quiere de un perfil que existe para
    # que la pieza aguante carga y no para que se vea bien.
    sparse_infill_pattern="cubic",
    # Igual que Standard. Strong existe para que la pieza aguante, no para que
    # se vea, pero con 4 paredes cada cruce de travel cae sobre una pared que
    # ademas es gruesa: la cicatriz queda igual y el rodeo es proporcionalmente
    # mas barato que en un perfil de pared fina.
    reduce_crossing_wall="1",
    ensure_vertical_shell_thickness="ensure_all",
    infill_wall_overlap="25%",
    alternate_extra_wall="0",
    # Scarf joint. `conditional` hace que se aplique solo donde la pared es lo
    # bastante lisa (angulo > 155 grados): en una esquina viva el scarf se ve
    # peor que la costura normal, asi que ahi se abstiene.
    seam_slope_type="external",
    seam_slope_conditional="1",
    scarf_angle_threshold="155",

    # inner-outer-inner necesita 3 paredes o mas para significar algo: deposita
    # la exterior apoyada contra material ya solido de los dos lados, lo que
    # mejora precision y voladizos. Con wall_loops 2 no hay tercera pared y el
    # modo degenera al orden normal, asi que vive en los procesos que tienen
    # 3 o mas: aca (4) y Standard (3, y por herencia el de ABS). Fine y Draft
    # se quedan con 2 y por lo tanto con el orden normal.
    wall_sequence="inner-outer-inner wall",
)

# 0.28mm Draft: prototipos y piezas grandes. Limitado por caudal, no por
# velocidad: a 0.28 de capa cada mm de recorrido mueve mucho mas plastico.
DRAFT = replace(
    COMMON,
    name="0.28mm Draft " + SUF,
    inherits="0.28mm Extra Draft @MyKlipper",
    layer_height="0.28",
    initial_layer_print_height="0.25",
    line_width="0.45",
    initial_layer_line_width="0.5",
    outer_wall_line_width="0.42",
    inner_wall_line_width="0.48",
    top_surface_line_width="0.42",
    internal_solid_infill_line_width="0.45",
    sparse_infill_line_width="0.5",
    # Draft prioriza tiempo: la pared exterior se queda donde estaba y la
    # aceleracion vuelve a 1000. Si la pieza tiene que verse bien, va Standard.
    outer_wall_speed="50",
    outer_wall_acceleration="1000",
    inner_wall_speed="80",
    sparse_infill_speed="75",
    internal_solid_infill_speed="80",
    top_surface_speed="45",
    gap_infill_speed="40",
    internal_bridge_speed="60",
    bridge_speed="35",
    initial_layer_speed="25",
    initial_layer_infill_speed="55",
    overhang_1_4_speed="0",
    overhang_2_4_speed="40",
    overhang_3_4_speed="22",
    overhang_4_4_speed="10",
    wall_loops="2",
    top_shell_layers="3",
    top_shell_thickness="0.84",
    bottom_shell_layers="2",
    bottom_shell_thickness="0.56",
    sparse_infill_density="10%",
    # Una capa de 0.28 de aire.
    support_top_z_distance="0.28",
    support_bottom_z_distance="0.28",
    # infill_combination se queda en 0 (el valor de COMMON). Estaba en 1 y no
    # hacia nada: combinar dos capas de 0.28 da 0.56 mm de altura, mas que el
    # diametro del nozzle, asi que Orca no combina. Solo tendria efecto en un
    # perfil de capa fina, donde 2 x altura entre en 0.4.
)


# 0.20mm ABS: el mismo Standard, con lo que el ABS necesita para sobrevivir a
# una impresora SIN ENCERRAMIENTO.
#
# Existe porque habia una grieta en la arquitectura de este repo. Las notas del
# filamento ABS decian "Obligatorio en el proceso: Brim outer_only 8mm" y
# "Recomendado: Draft shield" -- pero brim_type y draft_shield son claves de
# PROCESO, y en OrcaSlicer un filamento no puede pisar una clave de proceso.
# O sea que la fuente de verdad documentaba un paso manual en la UI, sin
# verificacion, para el unico material donde los defaults del proceso estan
# realmente mal. Con esto vuelve a estar todo del lado que `check` mira.
#
# LO QUE NO SE TOCA, Y POR QUE: la velocidad y la aceleracion. Suena razonable
# imprimir ABS mas lento "para que no warpee", y es al reves. Sin caja, el modo
# de falla dominante es la delaminacion: la capa de abajo se enfria de mas
# antes de que llegue la de arriba. Ir mas lento le da MAS tiempo para
# enfriarse, no menos. Es el mismo razonamiento por el que el filamento va a
# 255 y no a 245. Bajar la aceleracion solo ayudaria si la pieza se despegara
# de la cama por inercia, y para eso esta el brim.
ABS_PROC = replace(
    STANDARD,
    name="0.20mm ABS " + SUF,
    # outer_only y no auto_brim: en ABS el brim no es una ayuda de adherencia
    # marginal, es lo que sostiene las esquinas contra el warp. Solo por fuera
    # porque un brim interno no aporta nada ahi y complica despegar la pieza.
    brim_type="outer_only",
    brim_width="8",
    # SIN PLANCHADO, aunque Standard lo tenga. Se heredaba sin querer, y es el
    # material donde peor se porta: con el ventilador entre 0 y 15% la cara
    # superior no esta rigida cuando el nozzle vuelve a pasarle por encima, asi
    # que arrastra material en vez de fundir el valle entre cordones y deja
    # marcas. Y son minutos extra con el nozzle merodeando sobre la pieza:
    # sin encerramiento, cada minuto de mas es mas gradiente termico.
    ironing_type="no ironing",
    # La pared de sacrificio que rodea la pieza. No calienta el aire, pero
    # corta la corriente: sin encerramiento, la mayor parte del gradiente que
    # delamina viene de aire moviendose, no de temperatura ambiente baja.
    draft_shield="enabled",
)

PROCESSES = [FINE, STANDARD, STRONG, DRAFT, ABS_PROC]


# ============================================================================
# FILAMENTOS
# ============================================================================
def _plates(temp: int, first: int) -> dict[str, tuple[str, ...]]:
    """Todas las variantes de placa con la misma temperatura: el perfil funciona
    sin importar que 'Bed type' este seleccionado en la UI."""
    out: dict[str, tuple[str, ...]] = {}
    for k in ("cool_plate", "eng_plate", "hot_plate", "textured_plate",
              "textured_cool_plate", "supertack_plate"):
        out[f"{k}_temp"] = (str(temp),)
        out[f"{k}_temp_initial_layer"] = (str(first),)
    return out


# Lo que comparten los cuatro filamentos Printalot.
FILAMENT_COMMON = Filament(
    filament_vendor=("Printalot",),
    filament_diameter=("1.75",),
    filament_extruder_variant=("Direct Drive Standard",),
    compatible_printers=COMPAT,
    slow_down_for_layer_cooling=("1",),
    reduce_fan_stop_start_freq=("1",),
    enable_overhang_bridge_fan=("1",),
    # El pressure advance lo pone KLIPPER, no el laminador: la macro
    # START_PRINT tiene la tabla por material (variable_pa en
    # versions/<CURRENT>/macros.cfg) y recibe MATERIAL=[filament_type].
    # Asi cualquier gcode hereda el PA correcto aunque no lo haya generado
    # OrcaSlicer.
    #
    # La clave `pressure_advance` de cada filamento sigue definida mas
    # abajo a proposito: es la fuente de verdad que `orca.py check` cruza
    # contra variable_pa para que no se desincronicen.
    #
    # Poner esto en ["1"] en un filamento es un override deliberado: Orca
    # emite su SET_PRESSURE_ADVANCE despues del macro y por lo tanto gana.
    # Sirve para experimentar con Calibration -> Pressure Advance sin tocar
    # el firmware. check lo reporta como aviso, no como error.
    enable_pressure_advance=("0",),
)


PLA = replace(
    FILAMENT_COMMON,
    name="Printalot PLA " + SUF,
    inherits="Generic PLA @System",
    filament_type=("PLA",),
    **_plates(60, 60),
    filament_density=("1.24",), filament_cost=("25",),
    # Caudal y temperatura son la misma variable vista de dos lados. El techo
    # NO lo pone [extruder] max_temp 300: eso es un limite de seguridad de
    # Klipper (lo que habilita ABS y PC), no cuanto plastico puede fundir el
    # bloque por segundo. Lo que manda ahi es la potencia del calentador y el
    # largo de la zona de fusion, que en el Sprite stock es corta.
    #
    # El PLA tiene ademas un techo propio del material: arriba de ~230 se
    # degrada dentro del hotend. Por eso 215 y no mas.
    #
    # 10 y no 11 a proposito: el proceso Standard pide 10.8 mm3/s en el relleno
    # (120 x 0.45 x 0.20). Contra un techo de 11 eso es el 98%, y el mecanismo
    # de auto-freno de Orca solo protege si el numero que lo dispara es honesto:
    # si el hotend real da 9, no frena nada y el relleno sub-extruye en
    # silencio. Con 10 el freno actua (infill a 111 mm/s, ~1% de tiempo) y el
    # perfil queda seguro de cuanto de la medicion. Cuando corras
    # Calibration -> Max Flowrate, subi esto al valor medido.
    filament_flow_ratio=("0.98",), filament_max_volumetric_speed=("10",),
    nozzle_temperature=("215",), nozzle_temperature_initial_layer=("220",),
    nozzle_temperature_range_low=("190",), nozzle_temperature_range_high=("230",),
    temperature_vitrification=("55",),
    close_fan_the_first_x_layers=("1",), full_fan_speed_layer=("3",),
    fan_min_speed=("100",), fan_max_speed=("100",), fan_cooling_layer_time=("45",),
    overhang_fan_speed=("100",), overhang_fan_threshold=("25%",),
    # 8 s y no 6. El 4020 radial stock de la S1 Pro es flojo, y en una capa de
    # 1-2 segundos (un cubo de calibracion, la punta de un cono, un detalle
    # fino) 6 s de piso no alcanzan a solidificar antes de que vuelva el
    # nozzle: la punta queda blanda y traslucida. El costo esta acotado a las
    # capas que YA son diminutas, asi que en tiempo absoluto es casi nada.
    slow_down_layer_time=("8",), slow_down_min_speed=("20",),
    pressure_advance=("0.04",),
    filament_notes=("Printalot PLA - 1.75mm\n"
                    "Perfil para Ender 3 S1 Pro + Klipper, nozzle 0.4.\n"
                    "Caudal maximo 10 mm3/s (hotend bimetalico stock, sin medir).\n"
                    "Chapa PEI lado LISO: 60 grados alcanza. Limpiar con alcohol isopropilico.\n"
                    "Pressure advance sugerido 0.04 (desactivado hasta calibrar).",),
)


PETG = replace(
    FILAMENT_COMMON,
    name="Printalot PETG " + SUF,
    inherits="Generic PETG @System",
    filament_type=("PETG",),
    **_plates(70, 70),
    filament_density=("1.27",), filament_cost=("30",),
    filament_flow_ratio=("0.95",), filament_max_volumetric_speed=("9",),
    nozzle_temperature=("240",), nozzle_temperature_initial_layer=("245",),
    nozzle_temperature_range_low=("220",), nozzle_temperature_range_high=("260",),
    temperature_vitrification=("80",),
    close_fan_the_first_x_layers=("2",), full_fan_speed_layer=("4",),
    fan_min_speed=("40",), fan_max_speed=("60",), fan_cooling_layer_time=("25",),
    overhang_fan_speed=("70",), overhang_fan_threshold=("25%",),
    slow_down_layer_time=("8",), slow_down_min_speed=("20",),
    filament_retraction_length=("0.8",), filament_retraction_speed=("30",),
    filament_deretraction_speed=("25",), filament_retract_before_wipe=("0%",),
    filament_wipe=("1",),
    pressure_advance=("0.06",),
    filament_notes=("Printalot PETG - 1.75mm\n"
                    "OJO con la chapa PEI del lado LISO: el PETG se suelda al PEI y arranca\n"
                    "pedazos de la lamina. Usar SIEMPRE stick de pegamento como separador\n"
                    "y despegar recien con la cama fria.\n"
                    "Cama a 70, no subir mas. Primera capa menos aplastada que en PLA.\n"
                    "Caudal maximo 9 mm3/s. Pressure advance sugerido 0.06.",),
)


ABS = replace(
    FILAMENT_COMMON,
    name="Printalot ABS " + SUF,
    inherits="Generic ABS @System",
    filament_type=("ABS",),
    **_plates(100, 100),
    filament_density=("1.04",), filament_cost=("30",),
    filament_flow_ratio=("0.98",), filament_max_volumetric_speed=("10",),
    # 255 y no 245. Sin encerramiento el modo de falla dominante del ABS no es
    # el warp de la cama (eso lo tapa el brim) sino la DELAMINACION: la capa de
    # abajo se enfria de mas antes de que llegue la de arriba y la pieza se
    # abre por una linea horizontal. Mas calor por capa compensa el que se
    # pierde al ambiente, y es la contramedida estandar. El material aguanta
    # hasta ~270 y el hotend hasta 300, asi que 255 sobra de margen.
    # El techo de caudal queda en 10: este margen se gasta entero en union de
    # capas, no en velocidad.
    nozzle_temperature=("255",), nozzle_temperature_initial_layer=("260",),
    nozzle_temperature_range_low=("230",), nozzle_temperature_range_high=("270",),
    temperature_vitrification=("100",), filament_shrink=("100.6%",),
    # EL MINIMO ES 15 Y NO 0, o sea que el ventilador no tiene rampa: arranca
    # en la capa 4 y se queda plano. No es pereza, son dos cosas de la maquina
    # que hacian que la rampa no existiera igual, y peor:
    #
    #   [fan] kick_start_time 0.5 -> Klipper larga el ventilador a 100% medio
    #     segundo cada vez que sube desde CERO. Con minimo 0 y maximo 15, el
    #     modelo de refrigeracion de Orca cruza el cero cada vez que cambia el
    #     tiempo de capa: cada cruce es medio segundo de aire a full sobre una
    #     pieza de ABS sin encerramiento, que es exactamente la perturbacion
    #     que todo este perfil existe para evitar.
    #   [fan] off_below 0.10 -> cualquier duty entre 1% y 9% se apaga entero.
    #     O sea que la mitad de abajo de la rampa 0-15 no se ejecutaba nunca:
    #     lo que el perfil declaraba como gradual, la maquina lo hacia binario.
    #
    # Con 15/15 el ventilador paga UN kick, en la capa 4, y despues no vuelve a
    # cruzar el umbral. Y 15% constante es lo que el ABS quiere de todas formas.
    close_fan_the_first_x_layers=("3",), full_fan_speed_layer=("0",),
    fan_min_speed=("15",), fan_max_speed=("15",), fan_cooling_layer_time=("20",),
    overhang_fan_speed=("25",), overhang_fan_threshold=("25%",),
    slow_down_layer_time=("15",), slow_down_min_speed=("20",),
    filament_retraction_length=("0.6",), filament_retraction_speed=("35",),
    activate_air_filtration=("0",),
    pressure_advance=("0.05",),
    filament_notes=("Printalot ABS - 1.75mm. IMPRESORA SIN ENCERRAMIENTO\n"
                    "Ventilador practicamente apagado (0-15%) para evitar delaminado.\n"
                    "Nozzle a 255, alto a proposito: sin caja la union entre capas es\n"
                    "el punto debil, y el calor extra por capa es lo que la sostiene.\n"
                    "Obligatorio en el proceso: Brim tipo outer_only con 8mm de ancho.\n"
                    "Recomendado: Draft shield = enabled en piezas altas o finas.\n"
                    "Cerrar puertas y ventanas del ambiente, cero corriente de aire.\n"
                    "Piezas mayores a ~100mm van a warpear igual sin caja.\n"
                    "Compensacion de contraccion 100.6%. El ABS emite VOC: ventilar despues.",),
)


TPU = replace(
    FILAMENT_COMMON,
    name="Printalot TPU Flex " + SUF,
    inherits="Generic TPU @System",
    filament_type=("TPU",),
    **_plates(45, 45),
    filament_density=("1.21",), filament_cost=("45",),
    filament_flow_ratio=("1",), filament_max_volumetric_speed=("3.5",),
    nozzle_temperature=("230",), nozzle_temperature_initial_layer=("230",),
    nozzle_temperature_range_low=("210",), nozzle_temperature_range_high=("240",),
    temperature_vitrification=("60",),
    close_fan_the_first_x_layers=("1",), full_fan_speed_layer=("2",),
    fan_min_speed=("50",), fan_max_speed=("80",), fan_cooling_layer_time=("20",),
    overhang_fan_speed=("80",), overhang_fan_threshold=("25%",),
    slow_down_layer_time=("6",), slow_down_min_speed=("10",),
    filament_retraction_length=("0.4",), filament_retraction_speed=("20",),
    filament_deretraction_speed=("20",), filament_retraction_minimum_travel=("3",),
    filament_retract_when_changing_layer=("0",), filament_z_hop=("0",),
    filament_wipe=("0",), filament_retract_before_wipe=("0%",),
    pressure_advance=("0.6",),
    filament_notes=("Printalot Flex / TPU (shore ~95A) - 1.75mm\n"
                    "El caudal maximo de 3.5 mm3/s es el que manda: Orca frena todas las\n"
                    "velocidades solo. No hace falta un proceso distinto.\n"
                    "Retraccion minima (0.4mm) y sin z-hop para que no se trabe el Sprite.\n"
                    "Cargar el filamento a mano, despacio, con el extrusor caliente.\n"
                    "Pressure advance sugerido 0.6 (el TPU necesita valores altos).",),
)


FILAMENTS = [PLA, PETG, ABS, TPU]


# ============================================================================
# API
# ============================================================================
# Seleccion que queda activa al abrir OrcaSlicer
DEFAULT_PROCESS = STANDARD.name
DEFAULT_FILAMENT = PLA.name
# curr_bed_type 3 = High Temp Plate = chapa PEI del lado liso
DEFAULT_BED_TYPE = "3"
# Filamentos de sistema que quedan visibles: solo los padres de los Printalot
KEEP_SYSTEM_FILAMENTS = [f.inherits for f in FILAMENTS]


class Entry(NamedTuple):
    """Un preset listo para volcar a disco."""

    kind: str
    name: str
    config: Preset
    base_id: str


def all_presets() -> list[Entry]:
    """Los nueve perfiles serializados, con el id del preset de fábrica del que
    deriva cada uno."""
    return [Entry(p.KIND, p.name, p.to_preset(), BASE_IDS[p.inherits])
            for p in (MACHINE, *PROCESSES, *FILAMENTS)]
