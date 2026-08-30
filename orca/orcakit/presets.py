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
    nozzle_diameter: SettingList = None
    nozzle_type: Setting = None
    extruder_type: SettingList = None
    printer_extruder_id: SettingList = None
    printer_extruder_variant: SettingList = None
    printable_area: SettingList = None
    printable_height: Setting = None
    bed_exclude_area: SettingList = None
    max_layer_height: SettingList = None
    min_layer_height: SettingList = None
    use_relative_e_distances: Setting = None
    use_firmware_retraction: Setting = None
    emit_machine_limits_to_gcode: Setting = None
    silent_mode: Setting = None
    scan_first_layer: Setting = None
    auxiliary_fan: Setting = None
    machine_max_speed_x: SettingList = None
    machine_max_speed_y: SettingList = None
    machine_max_speed_z: SettingList = None
    machine_max_speed_e: SettingList = None
    machine_max_acceleration_x: SettingList = None
    machine_max_acceleration_y: SettingList = None
    machine_max_acceleration_z: SettingList = None
    machine_max_acceleration_e: SettingList = None
    machine_max_acceleration_extruding: SettingList = None
    machine_max_acceleration_retracting: SettingList = None
    machine_max_acceleration_travel: SettingList = None
    machine_max_jerk_x: SettingList = None
    machine_max_jerk_y: SettingList = None
    machine_max_jerk_z: SettingList = None
    machine_max_jerk_e: SettingList = None
    machine_min_extruding_rate: SettingList = None
    machine_min_travel_rate: SettingList = None
    retraction_length: SettingList = None
    retract_length_toolchange: SettingList = None
    retraction_speed: SettingList = None
    deretraction_speed: SettingList = None
    retraction_minimum_travel: SettingList = None
    retract_before_wipe: SettingList = None
    retract_restart_extra: SettingList = None
    retract_restart_extra_toolchange: SettingList = None
    retract_when_changing_layer: SettingList = None
    wipe: SettingList = None
    wipe_distance: SettingList = None
    z_hop: SettingList = None
    z_hop_types: SettingList = None
    thumbnails: SettingList = None
    thumbnails_format: Setting = None
    machine_start_gcode: Setting = None
    machine_end_gcode: Setting = None
    before_layer_change_gcode: Setting = None
    layer_change_gcode: Setting = None
    machine_pause_gcode: Setting = None
    change_filament_gcode: Setting = None
    time_lapse_gcode: Setting = None
    default_print_profile: Setting = None
    default_filament_profile: SettingList = None
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
    compatible_printers: SettingList = None
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
    initial_layer_travel_acceleration: SettingList = None
    default_jerk: Setting = None
    travel_speed: Setting = None
    travel_speed_z: SettingList = None
    initial_layer_travel_speed: Setting = None
    small_perimeter_speed: SettingList = None
    small_perimeter_threshold: SettingList = None
    enable_overhang_speed: SettingList = None
    overhang_speed_classic: Setting = None
    overhang_totally_speed: SettingList = None
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
    ironing_type: Setting = None
    ironing_pattern: Setting = None
    ironing_flow: Setting = None
    ironing_speed: Setting = None
    ironing_spacing: Setting = None
    ironing_angle: Setting = None
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
    filament_vendor: SettingList = None
    filament_type: SettingList = None
    filament_diameter: SettingList = None
    filament_extruder_variant: SettingList = None
    compatible_printers: SettingList = None
    slow_down_for_layer_cooling: SettingList = None
    reduce_fan_stop_start_freq: SettingList = None
    enable_overhang_bridge_fan: SettingList = None
    enable_pressure_advance: SettingList = None
    cool_plate_temp: SettingList = None
    cool_plate_temp_initial_layer: SettingList = None
    eng_plate_temp: SettingList = None
    eng_plate_temp_initial_layer: SettingList = None
    hot_plate_temp: SettingList = None
    hot_plate_temp_initial_layer: SettingList = None
    textured_plate_temp: SettingList = None
    textured_plate_temp_initial_layer: SettingList = None
    textured_cool_plate_temp: SettingList = None
    textured_cool_plate_temp_initial_layer: SettingList = None
    supertack_plate_temp: SettingList = None
    supertack_plate_temp_initial_layer: SettingList = None
    filament_density: SettingList = None
    filament_cost: SettingList = None
    filament_flow_ratio: SettingList = None
    filament_max_volumetric_speed: SettingList = None
    nozzle_temperature: SettingList = None
    nozzle_temperature_initial_layer: SettingList = None
    nozzle_temperature_range_low: SettingList = None
    nozzle_temperature_range_high: SettingList = None
    temperature_vitrification: SettingList = None
    close_fan_the_first_x_layers: SettingList = None
    full_fan_speed_layer: SettingList = None
    fan_min_speed: SettingList = None
    fan_max_speed: SettingList = None
    fan_cooling_layer_time: SettingList = None
    overhang_fan_speed: SettingList = None
    overhang_fan_threshold: SettingList = None
    slow_down_layer_time: SettingList = None
    slow_down_min_speed: SettingList = None
    pressure_advance: SettingList = None
    filament_notes: SettingList = None
    filament_retraction_length: SettingList = None
    filament_retraction_speed: SettingList = None
    filament_deretraction_speed: SettingList = None
    filament_retract_before_wipe: SettingList = None
    filament_wipe: SettingList = None
    filament_shrink: SettingList = None
    activate_air_filtration: SettingList = None
    filament_retraction_minimum_travel: SettingList = None
    filament_retract_when_changing_layer: SettingList = None
    filament_z_hop: SettingList = None

    def _identity(self) -> Preset:
        return {"filament_settings_id": [self.name]}
