"""La validación cruzada entre los presets y la configuración de Klipper."""

import unittest
from unittest import mock

from pathlib import Path

from orcakit import checkcfg, klippercfg, profiles
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

    def test_recorre_las_ocho_secciones(self):
        from orca import klipper_dir  # el CLI resuelve versions/<CURRENT>
        r = checkcfg.run(klipper_dir(mock.Mock(klipper_dir=None)))
        secciones = {f.section for f in r.findings}
        self.assertEqual(len(secciones), 8, secciones)
        self.assertGreater(len(r.findings), 40)


class TestAceleraciones(unittest.TestCase):
    """El techo mecánico y el presupuesto de ringing son dos cosas distintas.

    Confundirlas es lo que hacía la versión anterior de esta regla, y costaba
    velocidad de travel gratis: `[printer] max_accel` no podía subir aunque
    ninguna aceleración de impresión se hubiera movido.
    """

    P = profiles.Process(
        name="Proceso", inherits="x",
        default_acceleration="1500",
        outer_wall_acceleration="700",
        sparse_infill_acceleration="100%",   # relativa: ya es fracción del techo
        travel_acceleration="3000",
        initial_layer_travel_acceleration=("3000",),
    )

    def _shaper(self, procesos, cfg):
        r = Report()
        with mock.patch.object(profiles, "PROCESSES", procesos):
            checkcfg._input_shaper(r, cfg)
        return r

    def test_accels_saltea_las_relativas(self):
        # "100%" no puede pasar un techo del que ya es una fracción.
        self.assertNotIn("sparse_infill_acceleration", checkcfg._accels(self.P))

    def test_el_techo_mecanico_incluye_el_travel(self):
        self.assertIn("travel_acceleration", checkcfg._accels(self.P))
        self.assertIn("initial_layer_travel_acceleration", checkcfg._accels(self.P))

    def test_el_presupuesto_de_ringing_excluye_el_travel(self):
        # El ringing de un desplazamiento por el aire no deja marca en la pieza.
        accels = checkcfg._print_accels(self.P)
        self.assertNotIn("travel_acceleration", accels)
        self.assertNotIn("initial_layer_travel_acceleration", accels)
        self.assertEqual(accels["default_acceleration"], 1500.0)

    def test_max_accel_alto_con_acels_de_impresion_bajas_pasa(self):
        # Regresion: antes esto fallaba solo por el valor de max_accel, aunque
        # el travel sea justamente lo que tiene que poder usarlo entero.
        cfg = {"printer": {"max_accel": "3000"}}
        r = self._shaper([self.P], cfg)
        self.assertEqual(r.failures, 0)

    def test_una_acel_de_impresion_sobre_el_techo_de_ringing_falla(self):
        malo = profiles.replace(
            self.P, inner_wall_acceleration=str(checkcfg.RINGING_ACCEL + 500))
        r = self._shaper([malo], {"printer": {"max_accel": "5000"}})
        fallas = [f for f in r.findings if f.level is Level.FAIL]
        self.assertEqual(len(fallas), 1)
        self.assertIn("inner_wall_acceleration", fallas[0].detail)

    def test_con_input_shaper_no_hay_techo_de_ringing(self):
        malo = profiles.replace(self.P, inner_wall_acceleration="6000")
        cfg = {"printer": {"max_accel": "6000"}, "input_shaper": {"shaper_freq_x": "40"}}
        self.assertEqual(self._shaper([malo], cfg).failures, 0)


class TestMacroMoves(unittest.TestCase):
    """Las coordenadas literales de un cuerpo de macro."""

    def test_toma_las_absolutas(self):
        body = "G90\nG1 Z50 F600\nG1 X8.0 Y10 F3000\n"
        self.assertEqual(checkcfg._macro_moves(body),
                         [("Z", 50.0), ("X", 8.0), ("Y", 10.0)])

    def test_saltea_las_relativas(self):
        # END_PRINT retrae y hace el wipe en G91: ahi un X5 es un
        # desplazamiento, no una posicion, y no hay contra que contrastarlo.
        body = "G91\nG1 X5 Y5 F3000\nG90\nG1 X0 Y220\n"
        self.assertEqual(checkcfg._macro_moves(body),
                         [("X", 0.0), ("Y", 220.0)])

    def test_saltea_los_valores_interpolados(self):
        body = "G90\nG1 Z{LAYER} F240\nG1 X8.0 Y140 E10 F1500\n"
        self.assertEqual(checkcfg._macro_moves(body),
                         [("X", 8.0), ("Y", 140.0)])

    def test_ignora_el_extrusor_y_el_avance(self):
        self.assertEqual(checkcfg._macro_moves("G1 E10 F1500\n"), [])

    def test_ignora_los_comentarios(self):
        self.assertEqual(checkcfg._macro_moves("; G1 X999\nG1 X1\n"),
                         [("X", 1.0)])


class TestMacroGeometry(unittest.TestCase):
    """Que ningun movimiento absoluto se salga del recorrido."""

    CFG = {
        "stepper_x": {"position_min": "-10", "position_max": "250"},
        "stepper_y": {"position_min": "-8", "position_max": "235"},
        "stepper_z": {"position_min": "-4", "position_max": "270"},
    }

    def _run(self, body):
        r = Report()
        checkcfg._macro_geometry(r, self.CFG, {"M": {"gcode": body}}, ("M",))
        return r

    def test_dentro_del_recorrido(self):
        r = self._run("G90\nG1 X8 Y140 F1500\nG1 Z50\n")
        self.assertEqual(r.failures, 0)

    def test_pasarse_de_position_max(self):
        r = self._run("G90\nG1 X300 Y10\n")
        self.assertEqual(r.failures, 1)

    def test_pasarse_de_position_min(self):
        r = self._run("G90\nG1 X-50 Y10\n")
        self.assertEqual(r.failures, 1)

    def test_position_min_ausente_vale_cero(self):
        # Klipper no declara position_min si es 0, y sin ese default un eje sin
        # la clave dejaria pasar cualquier coordenada negativa.
        r = Report()
        checkcfg._macro_geometry(
            r, {"stepper_x": {"position_max": "250"}},
            {"M": {"gcode": "G90\nG1 X-5\n"}}, ("M",))
        self.assertEqual(r.failures, 1)


class TestProcessCoherence(unittest.TestCase):
    """El hueco de soporte tiene que ser un numero entero de capas de aire."""

    def _run(self, layer, gap):
        r = Report()
        p = profiles.Process(name="P", layer_height=layer,
                             support_top_z_distance=gap,
                             support_bottom_z_distance=gap)
        with mock.patch.object(profiles, "PROCESSES", [p]):
            checkcfg._process_coherence(r)
        return r

    def test_multiplo_exacto(self):
        self.assertEqual(self._run("0.2", "0.2").failures, 0)
        self.assertEqual(self._run("0.12", "0.24").failures, 0)
        self.assertEqual(self._run("0.28", "0.28").failures, 0)

    def test_no_multiplo(self):
        # Es el defecto real que tenia el repo: un 0.2 unico en COMMON daba
        # 0.24 en Fine (0.12) y 0.28 en Draft (0.28).
        self.assertEqual(self._run("0.12", "0.2").failures, 2)
        self.assertEqual(self._run("0.28", "0.2").failures, 2)

    def test_cero_es_valido(self):
        self.assertEqual(self._run("0.2", "0").failures, 0)


class TestMacrosCompilan(unittest.TestCase):
    """Todo cuerpo de gcode_macro tiene que ser una plantilla Jinja valida.

    Klipper compila estas plantillas al arrancar: un {% if %} sin su {% endif %}
    no rompe al desplegar, rompe cuando la impresora intenta levantar la config
    y se queda en estado de error. Es barato atraparlo antes.
    """

    def test_los_macros_de_la_version_viva_compilan(self):
        try:
            import jinja2
        except ImportError:
            self.skipTest("jinja2 no instalado")
        root = Path(__file__).resolve().parents[2] / "versions"
        version = (root / "CURRENT").read_text().strip()
        cfg = klippercfg.load_dir(root / version).config
        # Los MISMOS delimitadores que usa Klipper. Con los de fabrica de
        # Jinja ({{ }}) esto solo validaria los bloques {% %} y dejaria pasar
        # cualquier expresion { } mal escrita, que es la mitad del riesgo.
        env = jinja2.Environment("{%", "%}", "{", "}",
                                 extensions=["jinja2.ext.do"])
        compilados = 0
        for section, keys in cfg.items():
            if not section.startswith(("gcode_macro ", "delayed_gcode ",
                                       "idle_timeout")):
                continue
            if (body := keys.get("gcode")) is None:
                continue
            with self.subTest(section=section):
                env.parse(body)
                compilados += 1
        self.assertGreater(compilados, 5)
