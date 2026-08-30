"""Resolución de la cadena de herencia de un preset instalado."""

from orcakit import flatten
from tests.fixtures import TempDirCase


class TestResolve(TempDirCase):

    def test_el_hijo_pisa_al_padre_y_hereda_el_resto(self):
        self.system("Custom", "process", "abuelo",
                    {"layer_height": "0.2", "outer_wall_speed": "120",
                     "travel_speed": "350"})
        self.system("Custom", "process", "padre",
                    {"inherits": "abuelo", "outer_wall_speed": "60"})
        self.user("process", "hijo", {"inherits": "padre", "layer_height": "0.12"})

        cfg, chain = flatten.resolve(self.tmp, "process", "hijo")
        self.assertEqual(cfg["layer_height"], "0.12")     # del hijo
        self.assertEqual(cfg["outer_wall_speed"], "60")   # del padre
        self.assertEqual(cfg["travel_speed"], "350")      # del abuelo
        self.assertEqual(chain, ["hijo", "padre", "abuelo"])

    def test_los_metadatos_no_son_configuracion(self):
        self.user("process", "solo", {
            "layer_height": "0.2", "type": "process", "version": "2.4.0.1",
            "from": "User", "is_custom_defined": "0", "setting_id": "abc"})
        cfg, _ = flatten.resolve(self.tmp, "process", "solo")
        self.assertEqual(cfg, {"layer_height": "0.2"})

    def test_el_preset_de_usuario_le_gana_al_de_sistema(self):
        self.system("Custom", "process", "mismo", {"layer_height": "0.28"})
        self.user("process", "mismo", {"layer_height": "0.12"})
        cfg, _ = flatten.resolve(self.tmp, "process", "mismo")
        self.assertEqual(cfg["layer_height"], "0.12")

    def test_un_preset_que_no_existe_se_reporta_con_su_nombre(self):
        with self.assertRaises(FileNotFoundError) as e:
            flatten.resolve(self.tmp, "filament", "Fantasma")
        self.assertIn("Fantasma", str(e.exception))

    def test_herencia_circular_no_es_una_recursion_infinita(self):
        # Antes esto daba RecursionError, que no dice nada de dónde está el ciclo.
        self.user("filament", "A", {"inherits": "B"})
        self.user("filament", "B", {"inherits": "A"})
        with self.assertRaises(ValueError) as e:
            flatten.resolve(self.tmp, "filament", "A")
        self.assertIn("A -> B -> A", str(e.exception))

    def test_un_preset_que_se_hereda_a_si_mismo(self):
        self.user("filament", "Solo", {"inherits": "Solo"})
        with self.assertRaises(ValueError):
            flatten.resolve(self.tmp, "filament", "Solo")
