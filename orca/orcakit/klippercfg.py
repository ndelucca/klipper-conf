"""Parser mínimo de archivos .cfg de Klipper.

`configparser` no sirve tal cual para esto:

  - Las secciones llevan espacios (`[gcode_macro START_PRINT]`), y aunque eso es
    un nombre de sección válido, el resto del formato no lo es.
  - Hay secciones sin ninguna clave (`[exclude_object]`), que configparser
    acepta pero que conviene distinguir de una sección ausente.
  - Los bloques `gcode:` son valores multilínea indentados con sintaxis Jinja,
    donde `{% if %}` y los comentarios `;` rompen el interpolador de configparser.
  - El bloque `#*#` que Klipper escribe con SAVE_CONFIG al final de printer.cfg
    hay que descartarlo entero: son claves con formato propio que no son
    configuración declarada por el usuario.

Devuelve {sección: {clave: valor}}, con los valores multilínea unidos por \\n y
sin la indentación común. Las secciones vacías quedan como {}.
"""

from pathlib import Path
from typing import NamedTuple

type Config = dict[str, dict[str, str]]

SAVE_CONFIG_MARK = "#*#"
MANAGED_FILES = ("hardware.cfg", "limits.cfg", "macros.cfg")


class LoadedConfig(NamedTuple):
    """Resultado de mergear los .cfg de un directorio de versión."""

    config: Config
    missing: list[str]
    """Archivos gestionados que no estaban."""
    clashes: list[str]
    """Secciones definidas en más de un archivo."""


def _strip_comment(value: str) -> str:
    """Saca el comentario inline de un valor de una sola línea.

    Klipper acepta `max_temp: 300 # Set to 300 for S1 Pro`. Solo se corta con el
    '#' precedido de espacio, para no romper un valor que lo lleve pegado.
    Se aplica únicamente a la primera línea: los cuerpos gcode multilínea se
    conservan tal cual, porque ahí ';' y '#' son parte del contenido.
    """
    i = value.find(" #")
    return value[:i].strip() if i >= 0 else value


def _separator(line: str) -> int | None:
    """Índice del ':' o '=' que separa clave de valor, el que venga primero.

    Tiene que estar después del primer carácter: una línea que arranca con el
    separador no declara ninguna clave.
    """
    found = [i for i in (line.find(":"), line.find("=")) if i > 0]
    return min(found) if found else None


def parse(text: str) -> Config:
    """Parsea el contenido de un .cfg. Devuelve {sección: {clave: valor}}."""
    out: Config = {}
    section: str | None = None
    key: str | None = None
    buf: list[str] = []

    def flush() -> None:
        if section is not None and key is not None:
            out[section][key] = "\n".join(buf).strip("\n")

    for raw in text.splitlines():
        # La cola de SAVE_CONFIG es estado que escribe Klipper, no configuración.
        if raw.startswith(SAVE_CONFIG_MARK):
            break

        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            continue

        # Comentario de línea completa. Adentro de un bloque gcode el ';' es
        # comentario de g-code y se conserva, porque el cuerpo se inspecciona.
        if stripped.startswith("#"):
            continue

        if stripped.startswith("[") and stripped.endswith("]"):
            flush()
            section = stripped[1:-1].strip()
            out.setdefault(section, {})
            key, buf = None, []
            continue

        if section is None:
            continue

        # Continuación de un valor multilínea: la línea viene indentada.
        if line[0] in " \t" and key is not None:
            buf.append(stripped)
            continue

        sep = _separator(line)
        if sep is None:
            continue

        flush()
        key = line[:sep].strip()
        rest = _strip_comment(line[sep + 1:].strip())
        buf = [rest] if rest else []

    flush()
    return out


def load(path: Path | str) -> Config:
    """Parsea un archivo."""
    return parse(Path(path).read_text(encoding="utf-8"))


def load_dir(path: Path | str, files: tuple[str, ...] = MANAGED_FILES) -> LoadedConfig:
    """Mergea los .cfg gestionados de un directorio de versión.

    Klipper no admite la misma sección en dos archivos, así que una colisión acá
    sería un error real de la config y por eso se reporta en vez de pisarse en
    silencio.
    """
    root = Path(path)
    config: Config = {}
    missing: list[str] = []
    clashes: list[str] = []
    for name in files:
        p = root / name
        if not p.is_file():
            missing.append(name)
            continue
        for section, keys in load(p).items():
            if section in config:
                clashes.append(section)
            config[section] = keys
    return LoadedConfig(config, missing, clashes)


def _param_refs(body: str) -> list[tuple[str, int]]:
    """(nombre, índice justo después del nombre) de cada `params.X` del cuerpo."""
    out: list[tuple[str, int]] = []
    mark = "params."
    i = 0
    while (i := body.find(mark, i)) >= 0:
        i += len(mark)
        j = i
        while j < len(body) and (body[j].isalnum() or body[j] == "_"):
            j += 1
        if j > i:
            out.append((body[i:j], j))
        i = j
    return out


def macro_params(body: str) -> set[str]:
    """Nombres de params.X que lee un cuerpo de gcode_macro."""
    return {name for name, _ in _param_refs(body)}


def macro_optional_params(body: str) -> set[str]:
    """Los params.X que el macro lee con un `|default(...)` en TODAS sus usos.

    La diferencia decide si que el laminador no mande un parámetro es un bug o
    una decisión. Sin default, un parámetro ausente rompe el macro en tiempo de
    impresión; con default, es la máquina eligiendo sola, que es justo lo que se
    quiere para las cosas que son de la máquina y no del gcode (el soak, por
    ejemplo). Antes las dos cosas eran el mismo aviso.
    """
    optional: dict[str, bool] = {}
    for name, end in _param_refs(body):
        rest = body[end:].lstrip()
        has_default = False
        if rest.startswith("|"):
            rest = rest[1:].lstrip()
            # El nombre del filtro tiene que terminar acá: sin esto, un
            # `|defaultish(...)` cuenta como default y el parámetro pasa por
            # opcional sin serlo.
            if rest.startswith("default"):
                has_default = rest[len("default"):].lstrip().startswith("(")
        optional[name] = optional.get(name, True) and has_default
    return {name for name, ok in optional.items() if ok}
