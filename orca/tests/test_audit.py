"""La auditoría de lo instalado. Necesita un directorio de datos de OrcaSlicer,
así que se arma uno sintético con los nombres reales de los nueve perfiles."""

from orcakit import audit, profiles
from orcakit.report import Level
from tests.fixtures import TempDirCase

# Un proceso manso: nada que se parezca a los valores de fabrica.
PROCESO = {
    "layer_height": "0.20", "outer_wall_speed": "45",
    "outer_wall_line_width": "0.42", "inner_wall_speed": "120",
    "inner_wall_line_width": "0.45", "internal_solid_infill_speed": "130",
    "internal_solid_infill_line_width": "0.42", "sparse_infill_speed": "140",
    "sparse_infill_line_width": "0.45", "top_surface_speed": "40",
    "top_surface_line_width": "0.40",
}
FILAMENTO = {
    "filament_max_volumetric_speed": ["10"], "nozzle_temperature": ["215"],
    "nozzle_temperature_initial_layer": ["220"], "hot_plate_temp": ["60"],
    "fan_min_speed": ["100"], "fan_max_speed": ["100"],
    "filament_retraction_length": ["nil"],
}


class AuditCase(TempDirCase):

    def install(self, proceso=None, filamento=None):
        self.user("machine", profiles.PRINTER, {"retraction_length": ["0.6"]})
        for p in profiles.PROCESSES:
            self.user("process", p.name, dict(PROCESO, **(proceso or {})))
        for f in profiles.FILAMENTS:
            self.user("filament", f.name, dict(FILAMENTO, **(filamento or {})))


class TestHerencia(AuditCase):

    def test_una_config_mansa_no_reporta_nada(self):
        self.install()
        r = audit.run(self.tmp)
        self.assertEqual(r.failures, 0)
        self.assertEqual(r.exit_code, 0)

    def test_un_valor_agresivo_de_fabrica_que_sobrevive_es_una_falla(self):
        # 200 mm/s de pared interior viene de la CoreXY con input shaper del
        # preset @MyKlipper y no tiene nada que hacer en una bed slinger.
        self.install(proceso={"inner_wall_speed": "200"})
        r = audit.run(self.tmp)
        self.assertEqual(r.failures, len(profiles.PROCESSES))
        self.assertEqual(r.exit_code, 1)
        self.assertTrue(all("inner_wall_speed" in f.detail
                            for f in r.findings if f.level is Level.FAIL))


class TestCaudal(AuditCase):

    def test_el_caudal_se_calcula_como_altura_por_ancho_por_velocidad(self):
        self.install()
        lines = [i.text for i in audit.run(self.tmp).items if hasattr(i, "text")]
        # 0.20 x 0.45 x 140 = 12.60 mm3/s, el mayor de los cinco features
        self.assertTrue(any("12.60 mm3/s" in l for l in lines), lines)

    def test_un_proceso_que_pide_mas_que_el_filamento_sale_marcado(self):
        self.install(filamento={"filament_max_volumetric_speed": ["5"]})
        lines = [i.text for i in audit.run(self.tmp).items if hasattr(i, "text")]
        self.assertTrue(any("FRENA" in l for l in lines))

    def test_si_entra_en_el_techo_del_filamento_no_frena(self):
        self.install(filamento={"filament_max_volumetric_speed": ["20"]})
        lines = [i.text for i in audit.run(self.tmp).items if hasattr(i, "text")]
        self.assertFalse(any("FRENA" in l for l in lines))


class TestMateriales(AuditCase):

    def test_la_retraccion_heredada_de_la_impresora_se_marca_con_asterisco(self):
        self.install()
        lines = [i.text for i in audit.run(self.tmp).items if hasattr(i, "text")]
        self.assertTrue(any("0.6*" in l for l in lines))

    def test_la_retraccion_propia_del_filamento_se_muestra_sin_asterisco(self):
        self.install(filamento={"filament_retraction_length": ["1.2"]})
        lines = [i.text for i in audit.run(self.tmp).items if hasattr(i, "text")]
        self.assertTrue(any("1.2" in l and "1.2*" not in l for l in lines))

    def test_un_valor_que_falta_dice_cual_es_y_de_que_perfil(self):
        self.install()
        self.user("process", profiles.PROCESSES[0].name,
                  {k: v for k, v in PROCESO.items() if k != "layer_height"})
        with self.assertRaises(ValueError) as e:
            audit.run(self.tmp)
        self.assertIn("layer_height", str(e.exception))
        self.assertIn(profiles.PROCESSES[0].name, str(e.exception))
