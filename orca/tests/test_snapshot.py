"""El invariante central del repo: cuándo dos versiones del snapshot dicen lo
mismo. Antes estaba escrito tres veces a mano, una por comando del CLI."""

import json
import unittest

from orcakit import snapshot
from tests.fixtures import TempDirCase


class TestEqual(unittest.TestCase):

    def test_un_json_con_las_claves_en_otro_orden_es_el_mismo(self):
        # OrcaSlicer reescribe los presets con su propio formato al cerrarse:
        # comparar literal marcaria diferencias que no lo son.
        a = '{"a": "1", "b": "2"}'
        b = '{\n  "b": "2",\n  "a": "1"\n}\n'
        self.assertTrue(snapshot.equal("machine/X.json", a, b))

    def test_un_json_con_otro_valor_no_es_el_mismo(self):
        self.assertFalse(snapshot.equal(
            "machine/X.json", '{"a": "1"}', '{"a": "2"}'))

    def test_un_json_ilegible_cae_a_comparacion_literal(self):
        self.assertTrue(snapshot.equal("m/X.json", "roto{", "roto{"))
        self.assertFalse(snapshot.equal("m/X.json", "roto{", "otro{"))

    def test_los_info_se_comparan_literales(self):
        # Son cinco lineas de texto plano: cualquier byte distinto importa.
        self.assertTrue(snapshot.equal("machine/X.info", "base_id = a\n", "base_id = a\n"))
        self.assertFalse(snapshot.equal("machine/X.info", "base_id = a\n", "base_id = b\n"))


class TestDiff(unittest.TestCase):

    def test_snapshots_iguales_son_falsy(self):
        t = {"machine/X.json": '{"a": "1"}'}
        self.assertFalse(snapshot.diff(t, dict(t)))

    def test_detecta_lo_que_falta_lo_que_sobra_y_lo_que_cambio(self):
        want = {"a.json": '{"k": "1"}', "b.json": '{"k": "2"}'}
        have = {"b.json": '{"k": "9"}', "c.json": '{"k": "3"}'}
        d = snapshot.diff(want, have)
        self.assertTrue(d)
        self.assertEqual(d.added, ["a.json"])
        self.assertEqual(d.removed, ["c.json"])
        self.assertEqual(d.changed, ["b.json"])


class TestBuildYRead(TempDirCase):

    def test_el_snapshot_son_dos_archivos_por_perfil(self):
        tree = snapshot.build()
        self.assertEqual(len(tree), 18)
        self.assertEqual(sum(1 for k in tree if k.endswith(".json")), 9)
        self.assertEqual(sum(1 for k in tree if k.endswith(".info")), 9)

    def test_el_json_es_canonico(self):
        text = snapshot.preset_json({"b": "2", "a": "1"})
        self.assertEqual(text, '{\n    "a": "1",\n    "b": "2"\n}\n')

    def test_el_snapshot_se_relee_identico(self):
        for rel, text in snapshot.build().items():
            p = self.tmp / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8", newline="\n")
        self.assertFalse(snapshot.diff(snapshot.build(), snapshot.read(self.tmp)))

    def test_read_ignora_lo_que_no_es_preset(self):
        (self.tmp / "machine").mkdir(parents=True)
        (self.tmp / "machine" / "X.json").write_text("{}", encoding="utf-8")
        (self.tmp / "machine" / "notas.txt").write_text("hola", encoding="utf-8")
        self.assertEqual(list(snapshot.read(self.tmp)), ["machine/X.json"])

    def test_el_info_lleva_el_base_id(self):
        self.assertIn("base_id = abc123", snapshot.info_text("abc123"))
