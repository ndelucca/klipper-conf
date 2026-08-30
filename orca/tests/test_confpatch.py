"""OrcaSlicer.conf es el archivo del usuario que este toolkit puede corromper:
si el MD5 que se escribe al final no verifica, OrcaSlicer descarta el archivo y
se pierde la configuración. De ahí que el checksum tenga tests propios."""

import json

from orcakit import confpatch
from tests.fixtures import TempDirCase

# El MD5 del cuerpo normalizado: CRLF pasados a LF y sin newlines al final. Las
# tres formas del mismo contenido tienen que dar el mismo hash.
CUERPO = '{"a": 1}'
DIGEST = "42B7B4F2921788EA14DAC5566E6F06D0"


class TestChecksum(TempDirCase):

    def test_digest_de_un_cuerpo_conocido(self):
        self.assertEqual(confpatch._digest(CUERPO), DIGEST)

    def test_crlf_y_lf_dan_el_mismo_digest(self):
        self.assertEqual(confpatch._digest(CUERPO.replace('}', '}\r\n')), DIGEST)

    def test_los_newlines_finales_no_cuentan(self):
        self.assertEqual(confpatch._digest(CUERPO + "\n\n\n"), DIGEST)

    def test_round_trip_deja_el_checksum_verificando(self):
        p = self.tmp / "OrcaSlicer.conf"
        digest = confpatch.write(p, {"app": {"version": "2.4"}, "filaments": []})
        cfg, declared, computed = confpatch.read(p)
        self.assertEqual(declared, computed)
        self.assertEqual(declared, digest)
        self.assertEqual(cfg["app"]["version"], "2.4")

    def test_write_usa_el_formato_de_orcaslicer(self):
        p = self.tmp / "OrcaSlicer.conf"
        confpatch.write(p, {"b": "2", "a": "1"})
        raw = p.read_bytes()
        self.assertIn(b"\r\n", raw)          # CRLF
        self.assertIn(b"\t", raw)            # indentado con tabs
        self.assertLess(raw.index(b'"a"'), raw.index(b'"b"'))  # claves ordenadas
        self.assertTrue(raw.rstrip().endswith(
            confpatch.MARK.encode() + confpatch._digest(
                json.dumps({"a": "1", "b": "2"}, indent="\t")).encode()))

    def test_archivo_sin_linea_de_checksum(self):
        p = self.tmp / "OrcaSlicer.conf"
        p.write_text('{"a": 1}', encoding="utf-8")
        cfg, declared, computed = confpatch.read(p)
        self.assertEqual(cfg, {"a": 1})
        self.assertIsNone(declared)
        self.assertIsNone(computed)

    def test_detecta_un_conf_editado_a_mano(self):
        p = self.tmp / "OrcaSlicer.conf"
        confpatch.write(p, {"a": "1"})
        p.write_text(p.read_text(encoding="utf-8").replace('"1"', '"9"'),
                     encoding="utf-8", newline="")
        _, declared, computed = confpatch.read(p)
        self.assertNotEqual(declared, computed)


class TestApplySelection(TempDirCase):

    ARGS = ("EnderS1ProKlipper", "0.20mm Standard", "Printalot PLA", "3",
            ["Generic PLA @System", "Generic PETG @System"])

    def test_sin_archivo_no_hace_nada(self):
        self.assertIsNone(
            confpatch.apply_selection(self.tmp / "no-existe.conf", *self.ARGS))

    def test_deja_una_sola_entrada_apuntando_a_nuestra_impresora(self):
        p = self.tmp / "OrcaSlicer.conf"
        confpatch.write(p, {
            "orca_presets": [{"machine": "Otra", "process": "X", "filament": "Y"}],
            "filaments": ["Generic PLA @System", "Generic PC @System"],
        })
        confpatch.apply_selection(p, *self.ARGS)
        cfg, declared, computed = confpatch.read(p)

        self.assertEqual(declared, computed, "el checksum tiene que verificar")
        self.assertEqual(len(cfg["orca_presets"]), 1)
        entry = cfg["orca_presets"][0]
        self.assertEqual(entry["machine"], "EnderS1ProKlipper")
        self.assertEqual(entry["process"], "0.20mm Standard")
        self.assertEqual(entry["curr_bed_type"], "3")
        self.assertEqual(cfg["presets"]["machine"], "EnderS1ProKlipper")
        # Solo sobreviven los filamentos de sistema que ya estaban visibles.
        self.assertEqual(cfg["filaments"], ["Generic PLA @System"])

    def test_si_no_quedaba_ninguno_visible_los_pone_todos(self):
        p = self.tmp / "OrcaSlicer.conf"
        confpatch.write(p, {"filaments": [], "orca_presets": []})
        confpatch.apply_selection(p, *self.ARGS)
        cfg, _, _ = confpatch.read(p)
        self.assertEqual(cfg["filaments"], list(self.ARGS[4]))
