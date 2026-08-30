"""La forma de un preset de OrcaSlicer: qué claves existen y de qué tipo son.

Este módulo NO tiene valores de configuración: eso vive en `profiles.py`, junto
a los comentarios que explican el porqué de cada uno. Acá está solamente la
forma, y lo que se gana con declararla es una garantía concreta:

    Process(oputer_wall_speed="45")   ->  TypeError en el import

Antes eso era un dict, así que un typo en una clave se serializaba igual,
OrcaSlicer lo ignoraba en silencio y el valor que creías haber puesto nunca
llegaba a la impresora. La dataclass lo convierte en un error ruidoso sin
necesidad de mypy ni de ninguna herramienta externa: la validación es del
propio `__init__`.

Un campo en None significa **ausente del JSON**, no vacío. Es la distinción que
usa OrcaSlicer para saber si un preset pisa un valor heredado o lo deja pasar,
así que `to_preset()` omite los None en vez de emitirlos como null.
"""

from dataclasses import dataclass, fields
from typing import ClassVar

type Setting = str | None
"""Una clave escalar del preset. None = ausente del JSON."""

type SettingList = tuple[str, ...] | None
"""Una clave que Orca guarda como lista, por dos motivos distintos: valores por
extrusor (`nozzle_diameter`) y valores genuinamente múltiples (`printable_area`,
`thumbnails`). Se declaran como tupla para que sean hashables y se puedan usar
de default directo, sin el ruido de un `field(default_factory=...)` por campo."""

type Preset = dict[str, str | list[str]]
"""Un preset ya serializado, listo para volcar a JSON."""

# El schema de preset de usuario que entiende esta versión de OrcaSlicer.
SCHEMA_VERSION = "2.4.0.1"

# Metadatos que OrcaSlicer espera en los nueve presets por igual. No son campos
# porque `from` es palabra reservada de Python y porque ninguno es configuración:
# describen el formato, no la impresora.
_METADATA: Preset = {
    "from": "User",
    "is_custom_defined": "0",
    "version": SCHEMA_VERSION,
}


class _Serializable:
    """Serialización compartida por los tres tipos de preset.

    Mixin sin campos a propósito: si fuera una dataclass base, `slots=True`
    declararía dos veces los slots heredados en cada subclase.
    """

    __slots__ = ()

    KIND: ClassVar[str]
    """El valor de la clave "type" del JSON."""

    name: Setting
    inherits: Setting

    def _identity(self) -> Preset:
        """La clave con la que OrcaSlicer identifica al preset.

        Es siempre el nombre, pero cada tipo la llama distinto y el filamento la
        guarda como lista. Derivarla acá evita que se desincronice del nombre.
        """
        raise NotImplementedError

    def to_preset(self) -> Preset:
        """Dict serializable. Omite los campos en None: ausente != vacío."""
        if not self.name or not self.inherits:
            raise ValueError(
                f"{type(self).__name__} sin name o sin inherits: {self.name!r} / "
                f"{self.inherits!r}. Un preset base no se puede serializar.")
        out: Preset = {"type": self.KIND, **_METADATA, **self._identity()}
        for f in fields(self):  # type: ignore[arg-type]
            value = getattr(self, f.name)
            if value is None:
                continue
            out[f.name] = list(value) if isinstance(value, tuple) else value
        return out


@dataclass(frozen=True, kw_only=True, slots=True)
class Machine(_Serializable):
    """El perfil de impresora: la geometría, los límites de movimiento y el
    contrato de g-code con los macros de Klipper."""

    KIND: ClassVar[str] = "machine"

    name: Setting = None
    inherits: Setting = None
    printer_variant: Setting = None
    printer_structure: Setting = None
    nozzle_diameter: PerExtruder = None
    nozzle_type: Setting = None
    extruder_type: PerExtruder = None
    printer_extruder_id: PerExtruder = None
    printer_extruder_variant: PerExtruder = None
    printable_area: PerExtruder = None
    printable_height: Setting = None
    bed_exclude_area: PerExtruder = None
    max_layer_height: PerExtruder = None
    min_layer_height: PerExtruder = None
    use_relative_e_distances: Setting = None
    use_firmware_retraction: Setting = None
    emit_machine_limits_to_gcode: Setting = None
    silent_mode: Setting = None
    scan_first_layer: Setting = None
    auxiliary_fan: Setting = None
    machine_max_speed_x: PerExtruder = None
    machine_max_speed_y: PerExtruder = None
    machine_max_speed_z: PerExtruder = None
    machine_max_speed_e: PerExtruder = None
    machine_max_acceleration_x: PerExtruder = None
    machine_max_acceleration_y: PerExtruder = None
    machine_max_acceleration_z: PerExtruder = None
    machine_max_acceleration_e: PerExtruder = None
    machine_max_acceleration_extruding: PerExtruder = None
    machine_max_acceleration_retracting: PerExtruder = None
    machine_max_acceleration_travel: PerExtruder = None
    machine_max_jerk_x: PerExtruder = None
    machine_max_jerk_y: PerExtruder = None
    machine_max_jerk_z: PerExtruder = None
    machine_max_jerk_e: PerExtruder = None
    machine_min_extruding_rate: PerExtruder = None
    machine_min_travel_rate: PerExtruder = None
    retraction_length: PerExtruder = None
    retract_length_toolchange: PerExtruder = None
    retraction_speed: PerExtruder = None
    deretraction_speed: PerExtruder = None
    retraction_minimum_travel: PerExtruder = None
    retract_before_wipe: PerExtruder = None
    retract_restart_extra: PerExtruder = None
    retract_restart_extra_toolchange: PerExtruder = None
    retract_when_changing_layer: PerExtruder = None
    wipe: PerExtruder = None
    wipe_distance: PerExtruder = None
    z_hop: PerExtruder = None
    z_hop_types: PerExtruder = None
    thumbnails: PerExtruder = None
    thumbnails_format: Setting = None
    machine_start_gcode: Setting = None
    machine_end_gcode: Setting = None
    before_layer_change_gcode: Setting = None
    layer_change_gcode: Setting = None
    machine_pause_gcode: Setting = None
    change_filament_gcode: Setting = None
    time_lapse_gcode: Setting = None
    default_print_profile: Setting = None
    default_filament_profile: PerExtruder = None
    print_host: Setting = None
    print_host_webui: Setting = None
    host_type: Setting = None
    extruder_clearance_radius: Setting = None
    extruder_clearance_height_to_rod: Setting = None
    extruder_clearance_height_to_lid: Setting = None

    def _identity(self) -> Preset:
        return {"printer_settings_id": self.name}


@dataclass(frozen=True, kw_only=True, slots=True)
class Process(_Serializable):
    """Un perfil de laminado: alturas de capa, velocidades y aceleraciones."""

    KIND: ClassVar[str] = "process"

    name: Setting = None
    inherits: Setting = None
    compatible_printers: PerExtruder = None
    initial_layer_print_height: Setting = None
    adaptive_layer_height: Setting = None
    default_acceleration: Setting = None
    outer_wall_acceleration: Setting = None
    inner_wall_acceleration: Setting = None
    internal_solid_infill_acceleration: Setting = None
    sparse_infill_acceleration: Setting = None
    top_surface_acceleration: Setting = None
    bridge_acceleration: Setting = None
    initial_layer_acceleration: Setting = None
    travel_acceleration: Setting = None
    initial_layer_travel_acceleration: PerExtruder = None
    default_jerk: Setting = None
    travel_speed: Setting = None
    travel_speed_z: PerExtruder = None
    initial_layer_travel_speed: Setting = None
    small_perimeter_speed: PerExtruder = None
    small_perimeter_threshold: PerExtruder = None
    enable_overhang_speed: PerExtruder = None
    overhang_speed_classic: Setting = None
    overhang_totally_speed: PerExtruder = None
    support_speed: Setting = None
    support_interface_speed: Setting = None
    wall_generator: Setting = None
    precise_outer_wall: Setting = None
    only_one_wall_top: Setting = None
    only_one_wall_first_layer: Setting = None
    detect_thin_wall: Setting = None
    detect_overhang_wall: Setting = None
    detect_narrow_internal_solid_infill: Setting = None
    ensure_vertical_shell_thickness: Setting = None
    seam_position: Setting = None
    staggered_inner_seams: Setting = None
    seam_gap: Setting = None
    seam_slope_type: Setting = None
    wipe_speed: Setting = None
    role_based_wipe_speed: Setting = None
    infill_wall_overlap: Setting = None
    top_bottom_infill_wall_overlap: Setting = None
    infill_direction: Setting = None
    minimum_sparse_infill_area: Setting = None
    gap_fill_target: Setting = None
    filter_out_gap_fill: Setting = None
    internal_solid_infill_pattern: Setting = None
    top_surface_pattern: Setting = None
    bottom_surface_pattern: Setting = None
    is_infill_first: Setting = None
    reduce_infill_retraction: Setting = None
    bridge_flow: Setting = None
    thick_bridges: Setting = None
    slowdown_for_curled_perimeters: Setting = None
    overhang_reverse: Setting = None
    overhang_reverse_threshold: Setting = None
    overhang_reverse_internal_only: Setting = None
    extra_perimeters_on_overhangs: Setting = None
    elefant_foot_compensation: Setting = None
    xy_hole_compensation: Setting = None
    xy_contour_compensation: Setting = None
    brim_type: Setting = None
    brim_width: Setting = None
    brim_object_gap: Setting = None
    skirt_loops: Setting = None
    draft_shield: Setting = None
    enable_support: Setting = None
    support_type: Setting = None
    support_style: Setting = None
    support_threshold_angle: Setting = None
    support_top_z_distance: Setting = None
    support_bottom_z_distance: Setting = None
    support_object_xy_distance: Setting = None
    support_base_pattern: Setting = None
    support_base_pattern_spacing: Setting = None
    support_interface_top_layers: Setting = None
    support_interface_bottom_layers: Setting = None
    support_interface_spacing: Setting = None
    support_line_width: Setting = None
    support_on_build_plate_only: Setting = None
    support_remove_small_overhang: Setting = None
    resolution: Setting = None
    enable_arc_fitting: Setting = None
    exclude_object: Setting = None
    gcode_label_objects: Setting = None
    enable_prime_tower: Setting = None
    timelapse_type: Setting = None
    print_sequence: Setting = None
    reduce_crossing_wall: Setting = None
    max_travel_detour_distance: Setting = None
    infill_combination: Setting = None
    layer_height: Setting = None
    line_width: Setting = None
    initial_layer_line_width: Setting = None
    outer_wall_line_width: Setting = None
    inner_wall_line_width: Setting = None
    top_surface_line_width: Setting = None
    internal_solid_infill_line_width: Setting = None
    sparse_infill_line_width: Setting = None
    outer_wall_speed: Setting = None
    inner_wall_speed: Setting = None
    sparse_infill_speed: Setting = None
    internal_solid_infill_speed: Setting = None
    top_surface_speed: Setting = None
    gap_infill_speed: Setting = None
    internal_bridge_speed: Setting = None
    bridge_speed: Setting = None
    initial_layer_speed: Setting = None
    initial_layer_infill_speed: Setting = None
    overhang_1_4_speed: Setting = None
    overhang_2_4_speed: Setting = None
    overhang_3_4_speed: Setting = None
    overhang_4_4_speed: Setting = None
    wall_loops: Setting = None
    top_shell_layers: Setting = None
    top_shell_thickness: Setting = None
    bottom_shell_layers: Setting = None
    bottom_shell_thickness: Setting = None
    sparse_infill_density: Setting = None
    sparse_infill_pattern: Setting = None
    seam_slope_conditional: Setting = None
    scarf_angle_threshold: Setting = None
    alternate_extra_wall: Setting = None
    wall_sequence: Setting = None

    def _identity(self) -> Preset:
        return {"print_settings_id": self.name}


@dataclass(frozen=True, kw_only=True, slots=True)
class Filament(_Serializable):
    """Un perfil de filamento: temperaturas, caudal, retracción y ventilación."""

    KIND: ClassVar[str] = "filament"

    name: Setting = None
    inherits: Setting = None
    filament_vendor: PerExtruder = None
    filament_type: PerExtruder = None
    filament_diameter: PerExtruder = None
    filament_extruder_variant: PerExtruder = None
    compatible_printers: PerExtruder = None
    slow_down_for_layer_cooling: PerExtruder = None
    reduce_fan_stop_start_freq: PerExtruder = None
    enable_overhang_bridge_fan: PerExtruder = None
    enable_pressure_advance: PerExtruder = None
    cool_plate_temp: PerExtruder = None
    cool_plate_temp_initial_layer: PerExtruder = None
    eng_plate_temp: PerExtruder = None
    eng_plate_temp_initial_layer: PerExtruder = None
    hot_plate_temp: PerExtruder = None
    hot_plate_temp_initial_layer: PerExtruder = None
    textured_plate_temp: PerExtruder = None
    textured_plate_temp_initial_layer: PerExtruder = None
    textured_cool_plate_temp: PerExtruder = None
    textured_cool_plate_temp_initial_layer: PerExtruder = None
    supertack_plate_temp: PerExtruder = None
    supertack_plate_temp_initial_layer: PerExtruder = None
    filament_density: PerExtruder = None
    filament_cost: PerExtruder = None
    filament_flow_ratio: PerExtruder = None
    filament_max_volumetric_speed: PerExtruder = None
    nozzle_temperature: PerExtruder = None
    nozzle_temperature_initial_layer: PerExtruder = None
    nozzle_temperature_range_low: PerExtruder = None
    nozzle_temperature_range_high: PerExtruder = None
    temperature_vitrification: PerExtruder = None
    close_fan_the_first_x_layers: PerExtruder = None
    full_fan_speed_layer: PerExtruder = None
    fan_min_speed: PerExtruder = None
    fan_max_speed: PerExtruder = None
    fan_cooling_layer_time: PerExtruder = None
    overhang_fan_speed: PerExtruder = None
    overhang_fan_threshold: PerExtruder = None
    slow_down_layer_time: PerExtruder = None
    slow_down_min_speed: PerExtruder = None
    pressure_advance: PerExtruder = None
    filament_notes: PerExtruder = None
    filament_retraction_length: PerExtruder = None
    filament_retraction_speed: PerExtruder = None
    filament_deretraction_speed: PerExtruder = None
    filament_retract_before_wipe: PerExtruder = None
    filament_wipe: PerExtruder = None
    filament_shrink: PerExtruder = None
    activate_air_filtration: PerExtruder = None
    filament_retraction_minimum_travel: PerExtruder = None
    filament_retract_when_changing_layer: PerExtruder = None
    filament_z_hop: PerExtruder = None

    def _identity(self) -> Preset:
        return {"filament_settings_id": [self.name]}
