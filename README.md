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
     hardware.cfg       pines, sensores, PID, offsets del probe, geometria
     limits.cfg         [printer] [gcode_arcs] [exclude_object] [idle_timeout]
     macros.cfg         START_PRINT / END_PRINT / M0 / m300
                        DESCARGAR_FILAMENTO / CALIBRAR_PID
     printer.cfg.example  plantilla del archivo mutable
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
   #*# SAVE_CONFIG ...         <- Klipper es dueño de esta cola
```

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

## La mitad de OrcaSlicer

```
 orca/
   orca.py              CLI unico
   src/profiles.py      fuente de verdad de los 9 perfiles
   presets/             snapshot versionado, generado
   docs/                el porque de cada valor
```

Un perfil de impresora, cuatro procesos y cuatro filamentos de Printalot,
calibrados contra esta máquina en particular. Ver `orca/README.md` para el
detalle y `orca/docs/` para el razonamiento detrás de cada número.

```sh
python orca/orca.py where     donde esta el directorio de datos de OrcaSlicer
python orca/orca.py build     regenera presets/ desde src/profiles.py
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

Los dos corren en CI en cada push.

## Cambiar algo

```
  editar versions/v3/limits.cfg   o   orca/src/profiles.py
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
- **`[input_shaper]` sin calibrar.** Es el cambio que más rinde: `max_accel`
  2000 es el techo contra el que están calibradas las aceleraciones de los 4
  procesos, y lo que destraba no es la velocidad sino la *distancia de
  aceleración*. Las secciones del acelerómetro USB están escritas y comentadas
  en `versions/v3/hardware.cfg`; el procedimiento, en `limits.cfg`. `check`
  falla si alguien sube la aceleración sin haber configurado el shaper.
- **Pressure advance sin calibrar fino.** Los valores de `variable_pa` son
  conservadores y típicos de un direct drive. El óptimo real de cada rollo sale
  de Calibration -> Pressure Advance en OrcaSlicer.
- **PID con los valores de fábrica.** El macro `CALIBRAR_PID` los mide a
  temperatura real de trabajo. El resultado queda en `SAVE_CONFIG`, igual que el
  `z_offset` y la malla.
- **Compensaciones dimensionales sin medir.** `xy_hole_compensation` en 0 y
  `elefant_foot_compensation` en 0.15 son genéricos. Están así a propósito: una
  compensación mal puesta se aplica a todos los agujeros de todas las piezas.
  Salen de Calibration -> Tolerance.
