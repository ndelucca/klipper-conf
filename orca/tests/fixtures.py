"""Un directorio de datos de OrcaSlicer sintético, para los tests que necesitan
resolver herencia sin tener OrcaSlicer instalado."""

import json
import tempfile
import unittest
from pathlib import Path


def write_preset(root: Path, kind: str, name: str, cfg: dict) -> None:
    d = root / kind
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.json").write_text(json.dumps(cfg), encoding="utf-8")


class TempDirCase(unittest.TestCase):
    """Base con un directorio temporal que se limpia solo."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def user(self, kind: str, name: str, cfg: dict) -> None:
        """Escribe un preset de usuario en el data dir sintético."""
        write_preset(self.tmp / "user" / "default", kind, name, cfg)

    def system(self, bundle: str, kind: str, name: str, cfg: dict) -> None:
        """Escribe un preset de fábrica."""
        write_preset(self.tmp / "system" / bundle, kind, name, cfg)
