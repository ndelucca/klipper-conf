"""La conversión de texto a número, que las dos mitades del repo comparten."""

import unittest

from orcakit import values


class TestNum(unittest.TestCase):

    def test_las_tres_convenciones(self):
        self.assertEqual(values.num("45"), 45.0)          # escalar de Orca
        self.assertEqual(values.num(["45"]), 45.0)        # por extrusor
        self.assertEqual(values.num("50%"), 50.0)         # relativo
        self.assertEqual(values.num("20, 5"), 20.0)       # par de Klipper

    def test_ausente_devuelve_el_default(self):
        self.assertIsNone(values.num(None))
        self.assertEqual(values.num(None, 5.0), 5.0)
        self.assertEqual(values.num([], 5.0), 5.0)

    def test_no_numerico_devuelve_el_default_en_vez_de_reventar(self):
        self.assertIsNone(values.num("Auto Lift"))
        self.assertEqual(values.num("brass", 0.0), 0.0)

    def test_require_falla_ruidosamente_y_dice_cual(self):
        self.assertEqual(values.require(["0.4"], "nozzle"), 0.4)
        with self.assertRaises(ValueError) as e:
            values.require(None, "layer_height de Fine")
        self.assertIn("layer_height de Fine", str(e.exception))


class TestOtros(unittest.TestCase):

    def test_is_pct_distingue_relativo_de_absoluto(self):
        self.assertTrue(values.is_pct("50%"))
        self.assertTrue(values.is_pct(["50%"]))
        self.assertFalse(values.is_pct("50"))
        self.assertFalse(values.is_pct(None))

    def test_first_desenvuelve_la_convencion_por_extrusor(self):
        self.assertEqual(values.first(["0.4"]), "0.4")
        self.assertEqual(values.first("0.4"), "0.4")
        self.assertIsNone(values.first([]))
        self.assertIsNone(values.first(None))

    def test_pair_solo_acepta_dos_numeros(self):
        self.assertEqual(values.pair("20, 5"), (20.0, 5.0))
        self.assertIsNone(values.pair("20"))
        self.assertIsNone(values.pair("20, 5, 3"))
        self.assertIsNone(values.pair("a, b"))
