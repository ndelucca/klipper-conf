"""Conversión de los valores de texto de OrcaSlicer y Klipper a números.

Las dos mitades del repo guardan los números como texto, y cada una con su
convención:

    Orca      "45"        escalar
              ["45"]      por extrusor: una lista de un solo elemento
              "50%"       relativo a otro valor
    Klipper   "20, 5"     un par x,y en una sola clave

Antes esta conversión estaba escrita tres veces, una por módulo, y las tres
divergían en qué hacer ante un valor ausente: `audit` reventaba, `checkcfg`
devolvía None y `klippercfg` un default. Esa divergencia es justamente el
mecanismo por el que un valor que `audit` da por bueno pasa inadvertido para
`check`. Ahora hay una sola conversión con dos contratos explícitos: `num` para
cuando la ausencia es un caso previsto, `require` para cuando no lo es.
"""

type Value = str | list[str] | tuple[str, ...] | float | int | None


def first(value: Value) -> str | None:
    """Desenvuelve la convención por extrusor: ["45"] -> "45". None si está vacío."""
    if isinstance(value, (list, tuple)):
        return str(value[0]) if value else None
    return None if value is None else str(value)


def num(value: Value, default: float | None = None) -> float | None:
    """Primer número de un valor. `default` si no lo tiene.

    Tolera las tres convenciones a la vez, así que sirve para los dos lados:
    de ["50%"] saca 50.0 y de "20, 5" saca 20.0.
    """
    text = first(value)
    if text is None:
        return default
    text = text.split(",")[0].strip().removesuffix("%")
    try:
        return float(text)
    except ValueError:
        return default


def require(value: Value, what: str) -> float:
    """Igual que `num`, pero falla ruidosamente en vez de devolver un default.

    Se usa donde un valor ausente significa que el perfil está mal armado y no
    tiene sentido seguir calculando con un cero silencioso.
    """
    got = num(value)
    if got is None:
        raise ValueError(f"{what}: esperaba un número, encontré {value!r}")
    return got


def is_pct(value: Value) -> bool:
    """True si el valor es relativo ("50%") y no absoluto ("50")."""
    text = first(value)
    return text is not None and text.endswith("%")


def pair(value: Value) -> tuple[float, float] | None:
    """(x, y) de un valor de Klipper tipo "20, 5". None si no es un par."""
    text = first(value)
    if text is None:
        return None
    parts = text.split(",")
    if len(parts) != 2:
        return None
    try:
        return float(parts[0]), float(parts[1])
    except ValueError:
        return None
