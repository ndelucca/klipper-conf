"""La validación cruzada entre los presets y la configuración de Klipper."""

import unittest
from unittest import mock

from orcakit import checkcfg, profiles
from orcakit.presets import Filament
from orcakit.report import Level, Report
from tests.fixtures import TempDirCase

# Lo mínimo de [extruder] y [heater_bed] para poder correr la parte térmica.
TERMICO = {
    "extruder": {"max_temp": "300", "min_extrude_temp": "170"},
    "heater_bed": {"max_temp": "110"},
    "fan": {"kick_start_time": "0.5", "off_below": "0.10"},
}


class TestHelpers(unittest.TestCase):

    def test_area_toma_el_maximo_de_cada_eje(self):
        self.assertEqual(
            checkcfg._area(("0x0", "220x0", "220x220", "0x220")), (220.0, 220.0))

    def test_area_ignora_las_esquinas_ilegibles(self):
        self.assertEqual(checkcfg._area(("0x0", "basura", "10x20")), (10.0, 20.0))

    def test_area_vacia_no_revienta(self):
        self.assertEqual(checkcfg._area(None), (None, None))

    def test_call_saca_el_macro_y_sus_parametros(self):
        macro, params = checkcfg._call(
            "START_PRINT BED_TEMP=[x] MATERIAL=[y]\nG28\n")
        self.assertEqual(macro, "START_PRINT")
        self.assertEqual(params, {"BED_TEMP", "MATERIAL"})

    def test_call_con_gcode_vacio(self):
        self.assertEqual(checkcfg._call(""), (None, set()))
        self.assertEqual(checkcfg._call(None), (None, set()))


class TestTermico(unittest.TestCase):
    """El filamento pide temperaturas y duty de ventilador; la máquina decide
    si eso es posible."""

    def _run(self, filaments, cfg=None):
        r = Report()
        with mock.patch.object(profiles, "FILAMENTS", filaments):
            checkcfg._thermal(r, cfg or TERMICO)
        return r

    def test_un_filamento_sin_temperaturas_propias_avisa_en_vez_de_reventar(self):
        # Regresion: antes esto era un ValueError de max() sobre lista vacia, y
        # el validador moria con un traceback en vez de reportar.
        f = Filament(name="Hereda Todo", inherits="Generic PLA @System")
        r = self._run([f])
        avisos = [x for x in r.findings if x.level is Level.WARN]
        self.assertTrue(any("Hereda Todo" in x.what for x in avisos))
        self.assertEqual(r.failures, 0)

    def test_un_nozzle_por_encima_del_max_temp_es_una_falla(self):
        f = Filament(name="Imposible", inherits="x",
                     nozzle_temperature=("350",),
                     nozzle_temperature_initial_layer=("350",))
        self.assertEqual(self._run([f]).failures, 1)

    def test_un_nozzle_por_debajo_del_min_extrude_temp_es_una_falla(self):
        f = Filament(name="Frio", inherits="x",
                     nozzle_temperature=("150",),
                     nozzle_temperature_initial_layer=("150",))
        fallas = [x for x in self._run([f]).findings if x.level is Level.FAIL]
        self.assertTrue(any("min_extrude_temp" in x.what for x in fallas))

    def test_un_duty_que_off_below_apaga_es_una_falla(self):
        # Pedir 5% con off_below 10% es pedir un ajuste que no existe: el
        # ventilador queda apagado y el perfil miente.
        f = Filament(name="Sutil", inherits="x", nozzle_temperature=("215",),
                     nozzle_temperature_initial_layer=("215",),
                     fan_min_speed=("5",), fan_max_speed=("5",))
        fallas = [x for x in self._run([f]).findings if x.level is Level.FAIL]
        self.assertTrue(any("off_below" in x.what for x in fallas))

    def test_un_kick_start_corto_es_solo_un_aviso(self):
        f = Filament(name="X", inherits="x", nozzle_temperature=("215",),
                     nozzle_temperature_initial_layer=("215",),
                     fan_min_speed=("100",), fan_max_speed=("100",))
        cfg = TERMICO | {"fan": {"kick_start_time": "0.1", "off_below": "0.0"}}
        r = self._run([f], cfg)
        self.assertEqual(r.failures, 0)
        self.assertTrue(any("kick_start_time" in x.what
                            for x in r.findings if x.level is Level.WARN))


class TestRun(TempDirCase):

    def test_archivos_faltantes_se_reportan_sin_reventar(self):
        r = checkcfg.run(self.tmp)
        self.assertEqual(r.exit_code, 1)
        self.assertTrue(any("faltan" in f.detail for f in r.findings))

    def test_una_seccion_duplicada_entre_archivos_corta_la_validacion(self):
        (self.tmp / "hardware.cfg").write_text("[printer]\nmax_accel: 2000\n")
        (self.tmp / "limits.cfg").write_text("[printer]\nmax_accel: 5000\n")
        (self.tmp / "macros.cfg").write_text("")
        r = checkcfg.run(self.tmp)
        self.assertEqual(r.exit_code, 1)
        self.assertTrue(any("duplicadas" in f.what for f in r.findings))


class TestIntegracion(unittest.TestCase):
    """Contra la configuración real del repo, que es lo que corre en CI."""

    def test_recorre_las_seis_secciones(self):
        from orca import klipper_dir  # el CLI resuelve versions/<CURRENT>
        r = checkcfg.run(klipper_dir(mock.Mock(klipper_dir=None)))
        secciones = {f.section for f in r.findings}
        self.assertEqual(len(secciones), 6, secciones)
        self.assertGreater(len(r.findings), 40)
