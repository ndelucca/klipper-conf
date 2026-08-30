"""Acumulación y renderizado de los hallazgos de una validación.

`audit` y `checkcfg` calculaban, imprimían y decidían el exit code en una sola
pasada, lo que hacía imposible testear "¿el pressure advance coincide?" sin
capturar stdout. Acá se corta esa mezcla: las validaciones devuelven un `Report`
—datos— y el CLI lo renderiza.

Un reporte es una secuencia ordenada de dos cosas: hallazgos tipados, que son lo
que se testea y lo que decide el exit code, y líneas literales, para las tablas
de `audit` que no son un ok/falla sino datos para mirar.
"""

from dataclasses import dataclass, field
from enum import StrEnum

BAR = "=" * 78


class Level(StrEnum):
    """Qué tan grave es un hallazgo. Solo FAIL cambia el exit code."""

    OK = "ok"
    WARN = "aviso"
    FAIL = "FALLA"


@dataclass(frozen=True, slots=True)
class Finding:
    """Una comprobación con su resultado."""

    level: Level
    section: str
    what: str
    detail: str = ""
    spaced: bool = False
    """Si va precedido de una línea en blanco, para agrupar visualmente."""


@dataclass(frozen=True, slots=True)
class Line:
    """Texto literal: encabezados, tablas, separadores."""

    text: str = ""


type Item = Finding | Line

# Tolerancia al comparar números que vienen de dos parseos de texto distintos.
EPSILON = 1e-9


@dataclass(slots=True)
class Report:
    """Los hallazgos de una validación, en orden."""

    items: list[Item] = field(default_factory=list)
    _section: str = ""
    _spaced: bool = False

    # -- construcción -------------------------------------------------------
    def line(self, text: str = "") -> None:
        self.items.append(Line(text))

    def section(self, title: str) -> None:
        self.items += [Line(""), Line(BAR), Line(title), Line(BAR)]
        self._section = title

    def gap(self) -> None:
        """Separa el próximo hallazgo del anterior con una línea en blanco."""
        self._spaced = True

    def add(self, level: Level, what: str, detail: str = "") -> None:
        self.items.append(Finding(level, self._section, what, detail, self._spaced))
        self._spaced = False

    def ok(self, what: str, detail: str = "") -> None:
        self.add(Level.OK, what, detail)

    def warn(self, what: str, detail: str = "") -> None:
        self.add(Level.WARN, what, detail)

    def fail(self, what: str, detail: str) -> None:
        self.add(Level.FAIL, what, detail)

    # -- comprobaciones numéricas -------------------------------------------
    def equal(self, what: str, orca: float | None, klipper: float | None,
              detail: str = "") -> None:
        """Los dos lados tienen que declarar el mismo número."""
        if orca is None or klipper is None:
            self.fail(what, f"falta un lado (orca={orca} klipper={klipper})")
        elif abs(orca - klipper) < EPSILON:
            self.ok(what, detail or f"{orca:g}")
        else:
            self.fail(what, f"orca={orca:g}  klipper={klipper:g}")

    def at_most(self, what: str, value: float | None, ceiling: float | None,
                detail: str = "") -> None:
        """El valor de Orca tiene que entrar en el techo que impone Klipper."""
        if value is None or ceiling is None:
            self.fail(what, f"falta un lado (orca={value} klipper={ceiling})")
        elif value <= ceiling + EPSILON:
            self.ok(what, detail or f"{value:g} <= {ceiling:g}")
        else:
            self.fail(what, f"{value:g} excede el límite {ceiling:g}")

    # -- resultado ----------------------------------------------------------
    @property
    def findings(self) -> list[Finding]:
        return [i for i in self.items if isinstance(i, Finding)]

    def count(self, level: Level) -> int:
        return sum(1 for f in self.findings if f.level is level)

    @property
    def failures(self) -> int:
        return self.count(Level.FAIL)

    @property
    def warnings(self) -> int:
        return self.count(Level.WARN)

    @property
    def exit_code(self) -> int:
        return 1 if self.failures else 0


def render(report: Report) -> str:
    """El reporte como texto para la terminal."""
    out: list[str] = []
    for item in report.items:
        if isinstance(item, Line):
            out.append(item.text)
            continue
        if item.spaced:
            out.append("")
        out.append(f"  {item.level.value:<8}{item.what:<44} {item.detail}".rstrip())
    return "\n".join(out)
