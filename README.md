# nd.printer

Configuración completa de una **Ender 3 S1 Pro con Klipper** sobre una Raspberry
Pi 3B+ (MainsailOS). Las dos mitades del sistema viven acá porque están acopladas.

```
 versions/          la maquina      -> se despliega a la Raspberry con Ansible
 orca/              el laminador    -> se instala en cualquier PC cliente
```

## Por qué están en el mismo repo

Los machine limits del perfil de OrcaSlicer son un espejo literal de la sección
`[printer]` de la config de Klipper. El start gcode es un contrato con la firma
del macro `START_PRINT`. `enable_arc_fitting` solo es seguro si
`[gcode_arcs] resolution` es lo bastante fina. El pressure advance de cada
filamento tiene que coincidir con la tabla del macro.

Nada de eso lo verifica OrcaSlicer, ni Klipper, ni un humano leyendo dos repos.
Lo verifica un comando:

```sh
python orca/orca.py check
```

Que falla, con el detalle exacto, apenas las dos mitades dejan de coincidir.

## Quién manda sobre qué

El criterio con el que está repartida la configuración:

```
 MAQUINA     -> Klipper, siempre.
               limites, cinematica, input shaper, arcos, malla de cama, macros

 OBJETO      -> el laminador, siempre.
               capas, perimetros, relleno, soportes, velocidad por feature

 MATERIAL    -> repartido a proposito.
               temperaturas y caudal en Orca (se calibran con sus herramientas)
               pressure advance en Klipper (para que cualquier gcode lo herede)
```

## La mitad de Klipper

```
 versions/
   CURRENT              contiene el nombre de la version viva. Fuente de verdad
   v1/  v2/             congeladas, referencia historica
   v3/
     hardware.cfg       pines, sensores, geometria, offsets X/Y del probe.
                        NO lleva PID ni z_offset: ver "las semillas" abajo
     limits.cfg         [printer] [gcode_arcs] [exclude_object] [idle_timeout]
     macros.cfg         START_PRINT / END_PRINT / M0 / m300
                        DESCARGAR_FILAMENTO / CALIBRAR_PID_NOZZLE
                        CALIBRAR_PID_CAMA
     printer.cfg.example  plantilla del mutable, con las semillas de
                        control/PID y z_offset
     firmware/          binario del MCU y su build config
```

El corte es deliberado: **`limits.cfg` es exactamente lo que tiene un espejo del
lado de OrcaSlicer**, y por eso es lo que valida `check`. `hardware.cfg` describe
la máquina física y al laminador no le importa.

### El truco de printer.cfg

Klipper escribe. Al final de `printer.cfg` mantiene un bloque `SAVE_CONFIG` con
la malla de cama, el `z_offset` del probe y los PID. Cualquier despliegue que
sobrescriba ese archivo borra calibraciones.

La solución es invertir cuál es el archivo mutable:

```
 printer.cfg          NO versionado, vive solo en la Pi, modo 0644
   [include hardware.cfg]      \
   [include limits.cfg]         |  versionados, modo 0444,
   [include mainsail.cfg]       |  los escribe Ansible
   [include macros.cfg]        /

   [extruder]  control + PID    <- semillas de lo que Klipper calibra:
   [heater_bed] control + PID      tienen que estar ACA, no en un include
   [bltouch]   z_offset

   #*# SAVE_CONFIG ...          <- Klipper es dueño de esta cola
```

### Por qué las semillas no pueden vivir en un include

Esto no es una preferencia de organización, es una regla de Klipper que
descubrimos de la peor manera:

```
SAVE_CONFIG section 'extruder' option 'control' conflicts with included value
```

**`SAVE_CONFIG` puede pisar un valor que esté en `printer.cfg`, pero se niega a
pisar uno que venga de un `[include]`.** De `printer.cfg` sabe borrarlo antes de
reescribirlo; de un include no puede, y en vez de dejar dos definiciones
contradictorias, aborta. El resultado es que un `PID_CALIBRATE` o un
`PROBE_CALIBRATE` quedan imposibles de guardar, y peor: mientras haya un valor
pendiente, `SAVE_CONFIG` falla **para todo**, así que tampoco podés guardar la
malla.

Por eso `hardware.cfg` no tiene `control`, `pid_*` ni `z_offset`. Sí tiene
`x_offset` e `y_offset` del BLTouch, que son la posición física del probe en el
carro y no una calibración.

La malla es la excepción y no necesita semilla: `[bed_mesh default]` es una
sección que no existe en ningún include, así que no hay conflicto que resolver.

`mainsail.cfg` no está en este repo a propósito: en la Pi es un symlink a
`~/mainsail-config/mainsail.cfg`, el checkout upstream que mantiene el
`[update_manager mainsail-config]` de Moonraker.

### Desplegar a la impresora

Lo hace el rol `klipper_config` de
[nd.homelab](https://github.com/ndelucca/nd.homelab). No se copia a mano.

```sh
# ver el diff antes de aplicar
ansible-playbook playbooks/printers.yml -l ndelucca-raspberry-printer \
  --tags klipper_config --check --diff

ansible-playbook playbooks/printers.yml -l ndelucca-raspberry-printer \
  --tags klipper_config
```

El rol aborta si hay una impresión en curso, clona este repo en la Pi, hace
backup, preserva el bloque `SAVE_CONFIG`, escribe los `.cfg` en modo `0444`,
reinicia Klipper y espera a que `/printer/info` vuelva a `state: ready`. Si el
parser rechaza algo, falla mostrando el mensaje exacto y cómo volver atrás.

Para hacer rollback a una versión anterior sin tocar el repo:

```sh
ansible-playbook playbooks/printers.yml -l ndelucca-raspberry-printer \
  --tags klipper_config -e klipper_config_version=v2
```

## Calibrar la máquina

Hay tres cosas que solo se pueden medir con la impresora delante: los PID de los
dos calentadores, el `z_offset` del probe y la malla de cama. Klipper las mide y
las guarda **en la Pi**, en el bloque `SAVE_CONFIG` de `printer.cfg`.

**Ese resultado no vuelve solo al repositorio.** `printer.cfg` no está
versionado y el rol de Ansible lo crea una única vez (`force: false`), así que si
algún día reinstalás la Pi, el archivo se recrea desde `printer.cfg.example` con
las semillas viejas y **la calibración se pierde**. Por eso cada calibración
tiene un paso final que no es opcional: traer el número al repo.

```
  MAQUINA                                      REPO
  ───────                                      ────
  CALIBRAR_PID_NOZZLE                          versions/v3/
  CALIBRAR_PID_CAMA        SAVE_CONFIG           printer.cfg.example
  PROBE_CALIBRATE          escribe en   ──▶      (las semillas)
  BED_MESH_CALIBRATE       printer.cfg
                           en la Pi              ▲
                                                 │
                                    copiar a mano y commitear
```

La malla es la única excepción: son 36 números que cambian cada vez que tocás
los tornillos, no tiene sentido versionarla. Vive solo en la Pi y se rehace
cuando hace falta.

### El orden

Importa: el PID va **antes** que la malla. Si la temperatura oscila 2-3 °C
mientras sondeás, la cama se dilata y se contrae debajo del probe y esa
oscilación queda dentro de la malla.

```
 1.  CALIBRAR_PID_NOZZLE            ~5 min    pitido -> SAVE_CONFIG -> M107
 2.  CALIBRAR_PID_CAMA             ~10 min    pitido -> SAVE_CONFIG
 3.  PROBE_CALIBRATE                          TESTZ Z=-0.05 ... ACCEPT
                                              -> SAVE_CONFIG
 4.  M140 S60 / M104 S150 / esperar 10 min
     BED_MESH_CALIBRATE                       -> SAVE_CONFIG
 5.  llevar 1, 2 y 3 al repositorio           <- el paso que se olvida
```

Los dos macros de PID avisan solos cuando terminan: mensaje en la consola y dos
pitidos por el beeper. No hay que quedarse mirando.

**El paso 4 va en caliente y con soak de verdad.** `BED_MESH_CALIBRATE` sondea
la cama a la temperatura que tenga en ese momento, y una cama a 60 °C no tiene
la misma forma que fría. Los 10 minutos de espera tampoco son capricho: el
sensor está pegado abajo y marca 60 mucho antes de que el aluminio llegue al
equilibrio. Sondear a los 30 segundos mide una cama a mitad de camino.

### El paso 5, en concreto

Después de cada `SAVE_CONFIG`, Klipper deja los valores nuevos al final de
`printer.cfg` en la Pi. Se leen desde el editor de Mainsail o por ssh:

```sh
ssh <la-pi> 'tail -40 ~/printer_data/config/printer.cfg'
```

Vas a ver algo así:

```
#*# <---------------------- SAVE_CONFIG ---------------------->
#*# [extruder]
#*# control = pid
#*# pid_kp = 27.091
#*# pid_ki = 2.544
#*# pid_kd = 72.130
#*#
#*# [bltouch]
#*# z_offset = 3.420
```

Esos números van a `versions/v3/printer.cfg.example`, en el bloque de semillas,
respetando el nombre en mayúsculas que usa la config normal (`pid_Kp`, no
`pid_kp`):

```sh
$EDITOR versions/v3/printer.cfg.example
git commit -am "Update the PID seeds from the calibration of <fecha>"
git push
```

No hace falta desplegar: `printer.cfg` ya está creado en la Pi y el rol no lo
vuelve a tocar. El commit es para que **la próxima** Pi arranque de un número
medido y no de uno de fábrica.

### Cuándo rehacer cada una

```
 PID nozzle    si cambiás el hotend, el calentador o el termistor
 PID cama      si cambiás la cama o el termistor
 z_offset      si cambiás el probe, la chapa, o al nivelar la cama
 malla         cada vez que tocás los tornillos, o cada varios meses
```

---

## La mitad de OrcaSlicer

```
 orca/
   orca.py              CLI unico
   orcakit/             el toolkit: perfiles, validaciones y parsers
   orcakit/profiles.py  fuente de verdad de los 10 perfiles
   presets/             snapshot versionado, generado
   tests/               unittest de la stdlib, sin dependencias
   docs/                el porque de cada valor
```

Un perfil de impresora, cinco procesos y cuatro filamentos de Printalot,
calibrados contra esta máquina en particular. Ver `orca/README.md` para el
detalle y `orca/docs/` para el razonamiento detrás de cada número.

```sh
python orca/orca.py where     donde esta el directorio de datos de OrcaSlicer
python orca/orca.py build     regenera presets/ desde orcakit/profiles.py
python orca/orca.py install   instala presets/ en OrcaSlicer (con backup)
python orca/orca.py verify    compara lo instalado contra presets/
python orca/orca.py audit     audita caudales y herencia de lo instalado
python orca/orca.py check     valida los presets contra versions/<CURRENT>
```

`build --check` y `check` son cosas distintas y conviene no confundirlas:

| Comando | Qué detecta |
|---|---|
| `build --check` | que `presets/` quedó desactualizado respecto de `profiles.py` |
| `check` | que los presets dejaron de ser coherentes con la config de Klipper |

Los dos corren en CI en cada push, después de los tests del toolkit:

```sh
python -m unittest discover -s orca/tests -t orca
```

## Cambiar algo

```
  editar versions/v3/limits.cfg   o   orca/orcakit/profiles.py
        │
        ├─ python orca/orca.py build     regenera presets/
        ├─ python orca/orca.py check     falla si las mitades no coinciden
        ├─ python orca/orca.py audit     caudales y herencia
        ├─ git commit && git push
        │
        ├─ en la PC:  python orca/orca.py install
        └─ en la Pi:  ansible-playbook ... --tags klipper_config
```

El push va antes del despliegue a propósito: el rol clona este repo **en la
impresora**, así que lo que se despliega es siempre lo que está pusheado.

## El host de impresión

`orca.py install` inyecta la URL de Moonraker en el perfil de impresora, pero esa
URL **no está versionada**. Sale de la variable de entorno `ORCA_PRINT_HOST` o
del archivo `.printer-host`, que está gitignoreado.

El motivo es de seguridad, no de prolijidad: una instancia de Moonraker expuesta
suele quedar sin autenticación efectiva, y su API acepta gcode arbitrario, subida
y borrado de archivos, y apagado. Este repo es público.

## Pendiente

En orden de impacto. El detalle de cada uno está en la sección 8 de
`orca/docs/orcaslicer-ender3s1pro-klipper.md`.

- **Caudal máximo sin medir.** El techo del PLA (10 mm³/s) es una estimación
  conservadora, no una medición, y el mecanismo de auto-freno de OrcaSlicer solo
  protege si ese número es real. Es lo único de esta lista que puede estar
  afectando la calidad **ahora**. Sale de Calibration -> Max Flowrate.
- **Nivelación y malla, del lado de la máquina.** No cuestan un peso y
  condicionan todo lo demás: nivelar con `SCREWS_TILT_CALCULATE` en vez del
  método del papel, y recalibrar la malla **con la cama caliente** (una palpada
  en frío corrige una cama que no existe al imprimir).
- **`[input_shaper]` sin calibrar.** Es el único cambio que mejora calidad y
  velocidad a la vez: lo que destraba no es la velocidad sino la *distancia de
  aceleración*. Mientras no exista, las aceleraciones de impresión se quedan en
  el techo de ringing de 2000. Las secciones del acelerómetro USB están
  escritas y comentadas en `versions/v3/hardware.cfg`; el procedimiento, en
  `limits.cfg`. `check` falla si un proceso sube la aceleración de impresión sin
  el shaper puesto.
- **La frecuencia de resonancia de cada eje, sin medir.** La torre de ringing
  (Calibration -> Input Shaper) la da en 20 minutos y sin hardware. Los 700
  mm/s² de la pared exterior son hoy una intuición: la amplitud residual va como
  `a / (2*pi*f)^2`, así que sin `f` no se sabe si sobran o faltan.
- **Pressure advance sin calibrar fino.** Los valores de `variable_pa` son
  conservadores y típicos de un direct drive. El óptimo real de cada rollo sale
  de Calibration -> Pressure Advance en OrcaSlicer.
- **PID con los valores de fábrica.** `CALIBRAR_PID_NOZZLE` y
  `CALIBRAR_PID_CAMA` los miden a temperatura real de trabajo. Ver
  [Calibrar la máquina](#calibrar-la-máquina), incluido el paso de traer el
  resultado al repo.
- **Compensaciones dimensionales sin medir.** `xy_hole_compensation` en 0 y
  `elefant_foot_compensation` en 0.15 son genéricos. Están así a propósito: una
  compensación mal puesta se aplica a todos los agujeros de todas las piezas.
  Salen de Calibration -> Tolerance.
