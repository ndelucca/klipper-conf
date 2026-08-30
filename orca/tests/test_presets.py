"""Lo que garantizan las dataclasses de presets.py, y que los nueve perfiles
que arma profiles.py son coherentes entre sí."""

import unittest
from dataclasses import replace

from orcakit import profiles
from orcakit.presets import Filament, Machine, Process


class TestGarantiasDeLaDataclass(unittest.TestCase):
    """El motivo de que los presets sean dataclasses y no dicts."""

    def test_una_clave_mal_escrita_es_un_error_y_no_pasa_desapercibida(self):
        # Con un dict esto se serializaba igual, OrcaSlicer lo ignoraba en
        # silencio y el valor nunca llegaba a la impresora.
        with self.assertRaises(TypeError) as e:
            Process(name="X", inherits="Y", oputer_wall_speed="45")
        self.assertIn("oputer_wall_speed", str(e.exception))

    def test_replace_tambien_valida_las_claves(self):
        with self.assertRaises(TypeError):
            replace(profiles.COMMON, layer_hieght="0.2")

    def test_los_presets_son_inmutables(self):
        with self.assertRaises(Exception):
            profiles.MACHINE.printable_height = "300"  # type: ignore[misc]

    def test_un_preset_base_sin_nombre_no_se_puede_serializar(self):
        with self.assertRaises(ValueError):
            profiles.COMMON.to_preset()

    def test_los_campos_en_none_se_omiten_del_json(self):
        # None significa "ausente", que es como Orca sabe que no se pisa el
        # valor heredado. Emitirlo como null cambiaría el significado.
        p = Machine(name="X", inherits="Y", printable_height="270")
        self.assertNotIn("nozzle_diameter", p.to_preset())
        self.assertEqual(p.to_preset()["printable_height"], "270")

    def test_las_tuplas_se_serializan_como_listas(self):
        p = Machine(name="X", inherits="Y", nozzle_diameter=("0.4",))
        self.assertEqual(p.to_preset()["nozzle_diameter"], ["0.4"])

    def test_la_identidad_se_deriva_del_nombre(self):
        self.assertEqual(
            Machine(name="M", inherits="i").to_preset()["printer_settings_id"], "M")
        self.assertEqual(
            Process(name="P", inherits="i").to_preset()["print_settings_id"], "P")
        self.assertEqual(
            Filament(name="F", inherits="i").to_preset()["filament_settings_id"], ["F"])


class TestTodosLosPerfiles(unittest.TestCase):

    def test_all_presets_cubre_la_maquina_los_procesos_y_los_filamentos(self):
        # Derivado de las listas y no cableado a un numero: agregar un proceso
        # es una operacion normal de este repo, y no tiene por que romper un
        # test que no habla de eso.
        self.assertEqual(
            len(profiles.all_presets()),
            1 + len(profiles.PROCESSES) + len(profiles.FILAMENTS))

    def test_cada_proceso_declara_su_altura_de_capa(self):
        for p in profiles.PROCESSES:
            self.assertTrue(p.layer_height, f"{p.name} sin layer_height")

    def test_los_nombres_no_se_repiten(self):
        names = [e.name for e in profiles.all_presets()]
        self.assertEqual(len(names), len(set(names)))

    def test_todo_lo_que_se_hereda_tiene_su_base_id(self):
        for e in profiles.all_presets():
            self.assertTrue(e.base_id, f"{e.name} sin base_id")

    def test_solo_se_serializan_strings_y_listas_de_strings(self):
        # Es lo unico que entiende el schema de preset de OrcaSlicer.
        for e in profiles.all_presets():
            for k, v in e.config.items():
                with self.subTest(preset=e.name, clave=k):
                    if isinstance(v, list):
                        self.assertTrue(all(isinstance(x, str) for x in v))
                    else:
                        self.assertIsInstance(v, str)

    def test_todos_declaran_su_tipo_y_a_quien_heredan(self):
        for e in profiles.all_presets():
            self.assertEqual(e.config["type"], e.kind)
            self.assertIn("inherits", e.config)

    def test_los_procesos_y_filamentos_declaran_nuestra_impresora(self):
        for p in (*profiles.PROCESSES, *profiles.FILAMENTS):
            self.assertEqual(p.compatible_printers, (profiles.PRINTER,))

    def test_el_repo_publico_no_lleva_la_url_real(self):
        machine = profiles.MACHINE.to_preset()
        self.assertEqual(machine["print_host"], profiles.PLACEHOLDER_HOST)
        self.assertEqual(machine["print_host_webui"], profiles.PLACEHOLDER_HOST)

    def test_los_filamentos_de_sistema_que_se_conservan_son_los_padres(self):
        self.assertEqual(profiles.KEEP_SYSTEM_FILAMENTS,
                         [f.inherits for f in profiles.FILAMENTS])
