"""El parser de .cfg tiene cuatro reglas que no son obvias y que son la razón
por la que no se usa configparser. Cada una tiene su test."""

import unittest

from orcakit import klippercfg
from tests.fixtures import TempDirCase


class TestReglasDelFormato(unittest.TestCase):

    def test_seccion_con_espacios_en_el_nombre(self):
        cfg = klippercfg.parse("[gcode_macro START_PRINT]\ngcode:\n  G28\n")
        self.assertIn("gcode_macro START_PRINT", cfg)

    def test_seccion_vacia_no_es_lo_mismo_que_ausente(self):
        cfg = klippercfg.parse("[exclude_object]\n[fan]\nkick_start_time: 0.5\n")
        self.assertEqual(cfg["exclude_object"], {})
        self.assertNotIn("input_shaper", cfg)

    def test_bloque_gcode_multilinea_conserva_jinja_y_puntoycoma(self):
        cfg = klippercfg.parse(
            "[gcode_macro X]\n"
            "gcode:\n"
            "  {% if params.MATERIAL %}\n"
            "  M104 S200  ; calentar\n"
            "  {% endif %}\n")
        body = cfg["gcode_macro X"]["gcode"]
        self.assertEqual(
            body, "{% if params.MATERIAL %}\nM104 S200  ; calentar\n{% endif %}")

    def test_la_cola_de_save_config_se_descarta_entera(self):
        cfg = klippercfg.parse(
            "[extruder]\nnozzle_diameter: 0.4\n"
            "#*# <---------------------- SAVE_CONFIG ---------------------->\n"
            "#*# [extruder]\n"
            "#*# pid_kp = 21.5\n")
        self.assertEqual(cfg["extruder"], {"nozzle_diameter": "0.4"})


class TestComentariosYSeparadores(unittest.TestCase):

    def test_comentario_inline_solo_con_espacio_delante(self):
        cfg = klippercfg.parse("[extruder]\nmax_temp: 300 # para el S1 Pro\n")
        self.assertEqual(cfg["extruder"]["max_temp"], "300")

    def test_numeral_pegado_al_valor_no_es_comentario(self):
        cfg = klippercfg.parse("[x]\ncolor: ff00aa#solid\n")
        self.assertEqual(cfg["x"]["color"], "ff00aa#solid")

    def test_comentario_de_linea_completa_se_saltea(self):
        cfg = klippercfg.parse("[x]\n# esto no es una clave\nk: 1\n")
        self.assertEqual(cfg["x"], {"k": "1"})

    def test_separador_gana_el_que_aparece_primero(self):
        # "serial: /dev/x=y" -> la clave es serial, no "serial: /dev/x"
        cfg = klippercfg.parse("[mcu]\nserial: /dev/serial/by-id=abc\n")
        self.assertEqual(cfg["mcu"]["serial"], "/dev/serial/by-id=abc")
        cfg = klippercfg.parse("[mcu]\nrestart_method=command: now\n")
        self.assertEqual(cfg["mcu"]["restart_method"], "command: now")

    def test_linea_que_arranca_con_el_separador_no_declara_clave(self):
        self.assertEqual(klippercfg.parse("[x]\n: huerfano\n"), {"x": {}})

    def test_clave_sin_valor_queda_vacia(self):
        cfg = klippercfg.parse("[x]\ngcode:\n")
        self.assertEqual(cfg["x"]["gcode"], "")


class TestMacroParams(unittest.TestCase):

    def test_extrae_los_nombres_de_params(self):
        body = "{params.BED_TEMP|default(60)} y {params.MATERIAL}"
        self.assertEqual(klippercfg.macro_params(body), {"BED_TEMP", "MATERIAL"})

    def test_params_sin_nombre_no_cuenta(self):
        self.assertEqual(klippercfg.macro_params("{params.}"), set())

    def test_sin_params_devuelve_vacio(self):
        self.assertEqual(klippercfg.macro_params("G28\nG1 Z10"), set())


class TestLoadDir(TempDirCase):

    def test_reporta_los_archivos_que_faltan(self):
        (self.tmp / "hardware.cfg").write_text("[extruder]\nmax_temp: 300\n")
        loaded = klippercfg.load_dir(self.tmp)
        self.assertEqual(loaded.missing, ["limits.cfg", "macros.cfg"])
        self.assertIn("extruder", loaded.config)

    def test_una_seccion_en_dos_archivos_es_una_colision(self):
        # Klipper no lo admite, asi que pisarlo en silencio ocultaria el error.
        (self.tmp / "hardware.cfg").write_text("[printer]\nmax_accel: 2000\n")
        (self.tmp / "limits.cfg").write_text("[printer]\nmax_accel: 5000\n")
        (self.tmp / "macros.cfg").write_text("")
        self.assertEqual(klippercfg.load_dir(self.tmp).clashes, ["printer"])
