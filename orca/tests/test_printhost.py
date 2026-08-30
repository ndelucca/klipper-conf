"""La URL de la impresora es lo único que no se versiona: el repo es público y
una Moonraker expuesta suele quedar sin autenticación efectiva."""

import json
import os
import unittest
from unittest import mock

from orcakit import printhost
from tests.fixtures import TempDirCase

MACHINE_JSON = json.dumps({
    "name": "EnderS1ProKlipper",
    "print_host": "http://printer.local",
    "print_host_webui": "http://printer.local",
    "nozzle_diameter": ["0.4"],
})


class TestResolve(TempDirCase):

    def test_sin_nada_configurado_no_hay_host(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(printhost.resolve(self.tmp), (None, None))

    def test_la_variable_de_entorno_le_gana_al_archivo(self):
        (self.tmp / printhost.FILE_NAME).write_text("http://del-archivo\n")
        with mock.patch.dict(os.environ, {printhost.ENV_VAR: "http://del-entorno"}):
            url, origin = printhost.resolve(self.tmp)
        self.assertEqual(url, "http://del-entorno")
        self.assertIn(printhost.ENV_VAR, origin)

    def test_el_archivo_saltea_comentarios_y_lineas_en_blanco(self):
        (self.tmp / printhost.FILE_NAME).write_text(
            "# la URL de casa\n\n  https://impresora.example  \n")
        with mock.patch.dict(os.environ, {}, clear=True):
            url, origin = printhost.resolve(self.tmp)
        self.assertEqual(url, "https://impresora.example")
        self.assertIn(printhost.FILE_NAME, origin)

    def test_una_variable_vacia_no_cuenta_como_configurada(self):
        with mock.patch.dict(os.environ, {printhost.ENV_VAR: "   "}):
            self.assertIsNone(printhost.resolve(self.tmp).url)


class TestApply(unittest.TestCase):

    def test_inyecta_el_host_en_el_preset_de_maquina(self):
        out = json.loads(printhost.apply(
            "machine/EnderS1ProKlipper.json", MACHINE_JSON,
            "https://real.example", "EnderS1ProKlipper"))
        self.assertEqual(out["print_host"], "https://real.example")
        self.assertEqual(out["print_host_webui"], "https://real.example")
        self.assertEqual(out["nozzle_diameter"], ["0.4"])  # el resto pasa igual

    def test_no_toca_los_demas_presets(self):
        text = '{"name": "Printalot PLA"}'
        self.assertEqual(
            printhost.apply("filament/Printalot PLA.json", text, "https://x",
                            "EnderS1ProKlipper"), text)

    def test_sin_host_el_placeholder_queda_como_esta(self):
        self.assertEqual(
            printhost.apply("machine/EnderS1ProKlipper.json", MACHINE_JSON, None,
                            "EnderS1ProKlipper"), MACHINE_JSON)

    def test_el_resultado_sigue_siendo_json_canonico(self):
        # Si no, verify marcaria una diferencia de formato entre el repo y lo
        # instalado, que es justamente lo que apply existe para evitar.
        out = printhost.apply("machine/EnderS1ProKlipper.json", MACHINE_JSON,
                              "https://x", "EnderS1ProKlipper")
        self.assertTrue(out.endswith("\n"))
        keys = list(json.loads(out, object_pairs_hook=dict))
        self.assertEqual(keys, sorted(keys), "las claves tienen que quedar ordenadas")
