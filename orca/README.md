# Configuración de OrcaSlicer - Ender 3 S1 Pro + Klipper

Configuración reproducible de OrcaSlicer para una **Ender 3 S1 Pro** con
**Klipper** sobre Raspberry Pi 3B+, nozzle 0.4 y filamentos **Printalot**.

Clonás el repo, corrés un comando, y tenés exactamente los mismos 9 perfiles:
una impresora, cuatro procesos y cuatro filamentos.

- Documentación completa del *por qué* de cada valor: [`docs/orcaslicer-ender3s1pro-klipper.md`](docs/orcaslicer-ender3s1pro-klipper.md)
- Sin dependencias: solo la librería estándar de Python 3.8 o superior
- Funciona en Windows, macOS y Linux

---

## Uso rápido

```sh
git clone <este-repo> 3dprint
cd 3dprint

python orca/orca.py where      # confirma que encuentra tu OrcaSlicer

# opcional: la URL de tu impresora (ver "El host de impresión" mas abajo)
echo "https://mi-impresora.example" > .printer-host

# cerrar OrcaSlicer antes de instalar
python orca/orca.py install
python orca/orca.py verify     # confirma que quedó todo igual que en el repo
```

## Comandos

| Comando | Qué hace |
|---|---|
| `python orca/orca.py where` | Muestra dónde detectó el directorio de datos de OrcaSlicer y si la app está abierta |
| `python orca/orca.py build` | Regenera `presets/` desde `src/profiles.py` |
| `python orca/orca.py build --check` | No escribe nada: falla si `presets/` quedó desactualizado. Útil antes de commitear |
| `python orca/orca.py install` | Hace backup de lo que haya, instala `presets/` y deja la selección apuntando a estos perfiles |
| `python orca/orca.py install --dry-run` | Muestra qué archivos tocaría, sin escribir |
| `python orca/orca.py verify` | Compara archivo por archivo lo instalado contra el repo |
| `python orca/orca.py audit` | Resuelve la herencia de lo instalado y audita caudales, velocidades y temperaturas reales |
| `python orca/orca.py check` | Valida los presets contra la configuración de Klipper de `../versions/<CURRENT>/`. Falla si las dos mitades del repo se desincronizan |

Todos aceptan `--data-dir RUTA` si la autodetección falla, y respetan la
variable de entorno `ORCA_DATA_DIR`.

---

## Cómo está armado

El repo tiene **dos capas** que se mantienen sincronizadas:

```
 src/profiles.py            presets/                  OrcaSlicer
 ---------------            --------                  ----------
 definición en Python  -->  snapshot JSON        -->  instalación
 (fuente de verdad)         (lo que se versiona)      (tu máquina)

       orca.py build              orca.py install
                                  orca.py verify   <---- compara estas dos
```

- **`src/profiles.py`** es la fuente de verdad. Ahí están los valores con sus
  comentarios explicando por qué son esos y no otros.
- **`presets/`** es el snapshot exacto que consume OrcaSlicer. Se versiona para
  que el repo sirva aunque nunca corras `build`, y para que los diffs de git
  muestren el cambio real de configuración en cada commit.

`orca.py build --check` falla si las dos capas se desincronizan, así que no se
pueden separar sin darse cuenta.

### Árbol

```
 nd.printer/orca/
 |
 +-- orca.py                    CLI: where / build / install / verify / audit / check
 |
 +-- src/
 |   +-- profiles.py            FUENTE DE VERDAD: los 9 perfiles y sus comentarios
 |   +-- orcapaths.py           localizacion cross-platform del directorio de datos
 |   +-- localhost_.py          resolucion del host de impresion (no versionado)
 |   +-- confpatch.py           parcheo de OrcaSlicer.conf con recalculo del MD5
 |   +-- flatten.py             resuelve la cadena de herencia de un preset
 |   +-- audit.py               auditoria de caudales, herencia y temperaturas
 |
 +-- presets/                   SNAPSHOT versionado que consume OrcaSlicer
 |   +-- machine/               EnderS1ProKlipper
 |   +-- process/               Fine / Standard / Strong / Draft
 |   +-- filament/              Printalot PLA / PETG / ABS / TPU Flex
 |
 +-- docs/
 |   +-- orcaslicer-ender3s1pro-klipper.md    el por que de cada valor
 |   +-- artifact.html                        la misma doc en formato web
 |
 +-- src/klippercfg.py         parser minimo de los .cfg de Klipper
 +-- src/checkcfg.py           validacion cruzada contra versions/<CURRENT>

 (la configuracion de Klipper vive en ../versions/, y ../backup/ guarda
  lo que habia antes de cada install: los dos fuera de esta carpeta)
```

---

## El host de impresión

Es lo único de esta configuración que no se versiona. `presets/` guarda siempre
el placeholder `http://printer.local`, y la URL real se inyecta al instalar:

```
 1. variable de entorno ORCA_PRINT_HOST
 2. archivo .printer-host en la raiz del repo   (ignorado por git)
 3. nada: queda el placeholder
```

`orca.py verify` aplica la misma resolución, así que no marca una diferencia
falsa entre el repo y lo instalado.

> **Por qué no versionarla.** Una instancia de Moonraker publicada en internet
> suele quedar sin autenticación efectiva: el reverse proxy cae dentro de
> `trusted_clients`, así que Moonraker considera confiable a todo request que
> entre por el dominio. Se puede comprobar con `GET /access/info`: si devuelve
> `"login_required": false` y `"trusted": true`, la API está abierta y acepta
> gcode arbitrario, subida y borrado de archivos, y apagado de la máquina.
> Lo único que la protege es que nadie conozca la URL, y un repo público la
> deja indexada.
>
> Si ese es tu caso, lo que corresponde es cerrar el acceso (autenticación en
> el reverse proxy, `force_logins`, o directamente una VPN tipo Tailscale en
> vez de exponer el puerto).

---

## Cambiar algo

**No edites los perfiles desde la interfaz de OrcaSlicer.** Se pierden en el
próximo `install` y el repo deja de reflejar la realidad.

```sh
# 1. editar el valor en src/profiles.py
# 2. regenerar el snapshot
python orca/orca.py build

# 3. ver el impacto real (resuelve la herencia y recalcula caudales)
python orca/orca.py audit

# 4. instalar y commitear
python orca/orca.py install
git add -A && git commit -m "Bajar la aceleracion de pared exterior a 800"
```

El diff de git en `presets/` te muestra exactamente qué cambió en la
configuración, no solo qué cambió en el código.

---

## Qué toca `install` en tu sistema

```
 <data>/user/default/machine/     escribe   nuestros perfiles
 <data>/user/default/process/     REEMPLAZA el directorio entero
 <data>/user/default/filament/    REEMPLAZA el directorio entero
 <data>/user/default/_local/      ELIMINA   bundles importados
 <data>/OrcaSlicer.conf           parchea   la seleccion recordada + checksum MD5
```

Antes de tocar nada copia todo `user/default/` y el `OrcaSlicer.conf` a
`backup/<timestamp>/`. Con `--no-select` no toca la configuración de la app, y
con `--dry-run` no escribe nada.

`<data>` depende del sistema:

| Sistema | Ruta |
|---|---|
| Windows | `%APPDATA%\OrcaSlicer` |
| macOS | `~/Library/Application Support/OrcaSlicer` |
| Linux | `$XDG_CONFIG_HOME/OrcaSlicer` o `~/.config/OrcaSlicer` |
| Linux, Flatpak | `~/.var/app/io.github.softfever.OrcaSlicer/config/OrcaSlicer` |

---

## Restaurar la configuración anterior

Cada `install` copia lo que había a `backup/<timestamp>/` antes de escribir.
Esos backups son locales y no se versionan: son estado de una máquina concreta.

```sh
# cerrar OrcaSlicer
ls backup/                      # elegir el timestamp
rm -rf "<data>/user/default"
cp -r backup/<timestamp>/user "<data>/user"
cp backup/<timestamp>/OrcaSlicer.conf "<data>/OrcaSlicer.conf"
```

---

## Dependencias sobre la máquina

Estas dependencias **ya no se controlan a ojo**: las valida
`python orca/orca.py check` contra `../versions/<CURRENT>/`, y CI las corre en
cada push.

| Depende de | Dónde impacta |
|---|---|
| `[printer] max_accel` = 2000 | Todas las aceleraciones de los procesos están calibradas contra ese techo |
| `[printer]` max_velocity, max_z_velocity, square_corner_velocity | Espejados en los machine limits del perfil de impresora |
| Geometría de los steppers y del extruder | `printable_area`, `printable_height`, `nozzle_diameter` |
| `[gcode_arcs] resolution` <= 0.2 | Sin eso, `enable_arc_fitting` factea las curvas |
| `[exclude_object]` | Los procesos activan `exclude_object` |
| Las macros `START_PRINT` y `END_PRINT` | Son las que llama el start y end gcode, con sus parámetros |
| `variable_pa` en `START_PRINT` | Es quien pone el pressure advance; los valores de cada filamento tienen que coincidir |
| `max_temp` del hotend y de la cama | Techo de las temperaturas de cada filamento |

Si alguna deja de cumplirse, `check` falla diciendo exactamente cuál y con qué
valores de cada lado.

---

## Pendiente

`[input_shaper]` sigue sin calibrar, y el perfil está calibrado contra ese límite
a propósito: mientras no exista, `max_accel` se queda en 2000 y `check` falla si
alguien lo sube. La sección 8 de la documentación lista el orden de calibración y
exactamente qué valores subir después.

El pressure advance ya lo pone Klipper (tabla `variable_pa` en `macros.cfg`), pero
con valores conservadores. El óptimo de cada rollo sale de Calibration ->
Pressure Advance.
