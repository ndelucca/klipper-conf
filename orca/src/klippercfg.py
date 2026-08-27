# -*- coding: utf-8 -*-
"""Parser minimo de archivos .cfg de Klipper.

`configparser` no sirve tal cual para esto:

  - Las secciones llevan espacios (`[gcode_macro START_PRINT]`), y aunque eso es
    un nombre de seccion valido, el resto del formato no lo es.
  - Hay secciones sin ninguna clave (`[exclude_object]`), que configparser
    acepta pero que conviene distinguir de una seccion ausente.
  - Los bloques `gcode:` son valores multilinea indentados con sintaxis Jinja,
    donde `{% if %}` y `;` comentarios rompen el interpolador de configparser.
  - El bloque `#*#` que Klipper escribe con SAVE_CONFIG al final de printer.cfg
    hay que descartarlo entero: son claves con formato propio que no son
    configuracion declarada por el usuario.

Devuelve {seccion: {clave: valor}}, con los valores multilinea unidos por \\n y
sin la indentacion comun. Las secciones vacias quedan como {}.
"""
import pathlib

SAVE_CONFIG_MARK = "#*#"


def _sin_comentario(valor):
    """Saca el comentario inline de un valor de una sola linea.

    Klipper acepta `max_temp: 300 # Set to 300 for S1 Pro`. Solo se corta con el
    '#' precedido de espacio, para no romper un valor que lo lleve pegado.
    Se aplica unicamente a la primera linea: los cuerpos gcode multilinea se
    conservan tal cual, porque ahi ';' y '#' son parte del contenido.
    """
    i = valor.find(" #")
    return valor[:i].strip() if i >= 0 else valor


def parse(text):
    """Parsea el contenido de un .cfg. Devuelve {seccion: {clave: valor}}."""
    out = {}
    sec = None
    key = None
    buf = []

    def flush():
        if sec is not None and key is not None:
            out[sec][key] = "\n".join(buf).strip("\n")

    for raw in text.splitlines():
        # La cola de SAVE_CONFIG es estado que escribe Klipper, no configuracion.
        if raw.startswith(SAVE_CONFIG_MARK):
            break

        line = raw.rstrip()
        if not line.strip():
            continue

        stripped = line.strip()
        # Comentario de linea completa. Adentro de un bloque gcode el ';' es
        # comentario de g-code y se conserva, porque el cuerpo se inspecciona.
        if stripped.startswith("#"):
            continue

        if stripped.startswith("[") and stripped.endswith("]"):
            flush()
            sec = stripped[1:-1].strip()
            out.setdefault(sec, {})
            key, buf = None, []
            continue

        if sec is None:
            continue

        # Continuacion de un valor multilinea: la linea viene indentada.
        if line[0] in " \t" and key is not None:
            buf.append(stripped)
            continue

        sep = None
        for cand in (":", "="):
            i = line.find(cand)
            if i > 0 and (sep is None or i < sep[1]):
                sep = (cand, i)
        if sep is None:
            continue

        flush()
        key = line[:sep[1]].strip()
        rest = _sin_comentario(line[sep[1] + 1:].strip())
        buf = [rest] if rest else []

    flush()
    return out


def load(path):
    """Parsea un archivo."""
    return parse(pathlib.Path(path).read_text(encoding="utf-8"))


def load_dir(path, files=("hardware.cfg", "limits.cfg", "macros.cfg")):
    """Mergea los .cfg gestionados de un directorio de version.

    Devuelve (config, faltantes). Klipper no admite la misma seccion en dos
    archivos, asi que una colision aca seria un error real de la config y por eso
    se reporta en vez de pisarse en silencio.
    """
    root = pathlib.Path(path)
    cfg, faltantes, choques = {}, [], []
    for f in files:
        p = root / f
        if not p.is_file():
            faltantes.append(f)
            continue
        for sec, keys in load(p).items():
            if sec in cfg:
                choques.append(sec)
            cfg[sec] = keys
    return cfg, faltantes, choques


def num(value, default=None):
    """Primer numero de un valor. None si no lo tiene."""
    if value is None:
        return default
    txt = str(value).split(",")[0].strip()
    try:
        return float(txt)
    except ValueError:
        return default


def macro_params(body):
    """Nombres de params.X que lee un cuerpo de gcode_macro."""
    out = set()
    marca = "params."
    i = 0
    while True:
        i = body.find(marca, i)
        if i < 0:
            return out
        i += len(marca)
        j = i
        while j < len(body) and (body[j].isalnum() or body[j] == "_"):
            j += 1
        if j > i:
            out.add(body[i:j])
