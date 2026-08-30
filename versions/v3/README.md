# v3 - Split de la configuración en archivos gestionables

Fecha: 2026-08-27

## Qué cambia respecto de v2

v2 era un `printer.cfg` monolítico que había que copiar a mano a la Pi, más un
`macros.cfg` servido por symlink. v3 parte ese archivo en piezas con dueños
distintos, que es lo que permite desplegarlo desde Ansible sin pisar nunca lo que
Klipper escribe solo.

```
 printer.cfg          NO versionado. Vive solo en la Pi.
   [include ...]      cuatro lineas
   #*# SAVE_CONFIG    la malla de cama, el z_offset del probe, los PID

 hardware.cfg         pines, sensores, PID, offsets, geometria, nivelacion, buzzer
 limits.cfg           [printer] [gcode_arcs] [exclude_object] [idle_timeout]
 macros.cfg           START_PRINT / END_PRINT / M0 / m300 / CALIBRAR_*
 moonraker.conf       la tercera mitad. La despliega el mismo rol, pero con
                      handler y verificacion propios: reiniciar Moonraker tira
                      abajo la API con la que el rol verifica todo lo demas
```

El criterio del corte: **`limits.cfg` es todo lo que tiene un espejo del lado de
OrcaSlicer**, y por lo tanto lo valida `python orca/orca.py check`. `hardware.cfg`
es lo que describe la máquina física y no le importa al laminador.

`mainsail.cfg` sale del repo. En la Pi es un symlink a `~/mainsail-config/mainsail.cfg`,
el checkout upstream que mantiene el `[update_manager mainsail-config]` de Moonraker.
La copia que había en v1 y v2 nunca se usó.

## Cambios de comportamiento

| Qué | Antes | Ahora | Por qué |
|---|---|---|---|
| `[gcode_arcs] resolution` | ausente, o sea 1.0 mm | `0.1` | Con 1 mm, Klipper parte cada arco en cuerdas de 1 mm y deja una sagita de 0.064 mm en un radio de 2 mm. Se veía en bordes redondeados y agujeros chicos |
| `[idle_timeout]` | `timeout: 10` + `gcode: STATUS` | `timeout: 3600` + `TURN_OFF_HEATERS` / `M84` | `STATUS` no existe en esta máquina. El gcode default estaba pisado, así que los calentadores no se apagaban nunca y cada reposo tiraba un error |
| Malla de cama | la cargaba el start gcode de OrcaSlicer | la carga `START_PRINT` | La malla es de la máquina. Así cualquier gcode la hereda |
| Pressure advance | lo emitía OrcaSlicer por filamento | `START_PRINT MATERIAL=...` lo pone según el material | Mismo motivo. Un filamento de Orca puede pisarlo si se quiere experimentar |
| `[output_pin PB13]` | vivía en `macros.cfg` | vive en `hardware.cfg` | Es el buzzer, es hardware |

Todo lo demás (los 15 bloques de hardware, y los macros `M0`, `m300` y `END_PRINT`)
se migró byte a byte desde v2, verificado clave por clave.

## Cambios posteriores, dentro de v3

| Qué | Antes | Ahora | Por qué |
|---|---|---|---|
| `[printer] max_accel` | `2000` | `3000` | Estaba haciendo dos trabajos incompatibles: el techo **mecánico** de la máquina y el presupuesto de **ringing** de la superficie. Atados, el travel pagaba una restricción de calidad que no le corresponde: el ringing de un desplazamiento por el aire no deja marca. A 2000, llegar a los 250 mm/s de travel exigía 15.6 mm y casi ningún travel real es tan largo. Ninguna aceleración de impresión se movió: solo subió `travel_acceleration` |
| `M0` | `G1 E-5` sin reponer | sin retracción propia | El comentario decía "la repone el RESUME" y era falso. `RESUME` repone la retracción que hizo `PAUSE` (1 mm, de `mainsail.cfg`), no una que se le sumó después; y `RESTORE_GCODE_STATE` con `MOVE=0` reescribe la posición lógica de E sin mover el motor. El filamento quedaba 5 mm atrás y los primeros milímetros al reanudar salían huecos |
| `START_PRINT` | sin resetear overrides | `M220 S100` / `M221 S100` | Los factores de velocidad y flujo de Mainsail sobreviven entre impresiones. Tocás el slider al 130 % para salvar una pieza y la siguiente sale al 130 % sin que nada lo diga |
| `START_PRINT` subida a Z50 | `F240` (4 mm/s) | `F600` (10 mm/s) | Quedó del `max_z_velocity` viejo de 5. Son 40 mm: 10 s contra 4 s |
| `[bltouch]` | 1 lectura por punto | `samples: 2`, mediana, tolerancia 0.0125 con 3 reintentos | La primera capa de todas las impresiones descansaba sobre un único disparo del probe. No cuesta tiempo de impresión: la malla se guarda y se carga, no se re-palpa |
| `[bed_mesh] probe_count` | `6,6` (paso 39x44 mm) | `9,9` (paso 24x28 mm) | Con 6 puntos por eje la bicúbica inventaba el medio de cada celda, y una chapa de Ender 3 se deforma con longitud de onda menor que eso. Gratis, por el mismo motivo |
| Nivelación | `[bed_screws]` (papel) | `+ [screws_tilt_adjust]` | Había un probe y se nivelaba a mano. `SCREWS_TILT_CALCULATE` dice cuánto girar cada perilla, en minutos de reloj. La malla corrige el residuo de una cama nivelada; no la reemplaza, porque `fade_end: 10` la desvanece a partir de Z=10 |

Los cuatro tornillos son alcanzables por el probe: el caso apretado es el
derecho en X=195, que exige el nozzle en 195+48 = 243 contra un `position_max`
de 250. Entra, pero sin margen.

### La tanda siguiente

| Qué | Antes | Ahora | Por qué |
|---|---|---|---|
| `minimum_cruise_ratio` | ausente, o sea `0.5` | `0` | Es la otra mitad del argumento de `max_accel`. Klipper baja la aceleración para garantizar un 50 % de crucero, así que un movimiento sólo acelera durante el **25 %** de su largo y la velocidad pico va como `√(a·(1−r)·D)`: el default cuesta exactamente lo mismo que dividir `max_accel` por dos. La cuenta de la fila de arriba estaba subestimada: la distancia real para tocar 250 mm/s es `v²/(a·(1−r))`, o sea 62.5 mm con `a=2000` y 41.7 con `a=3000`, no 15.6 y 10.4 |
| `[gcode_arcs] resolution` | `0.1` | `0.2` | La sagita de un segmento de largo L sobre radio R es `L²/(8R)`. En el peor caso realista (un agujero de 2 mm, R=1) `0.1` daba 0.0013 mm, unas 80 veces más fino de lo que esta máquina posiciona, a cambio de 1100 segmentos por segundo que paga el planificador de Klipper en una Pi 3B+ |
| `[idle_timeout]` | apagaba siempre | guarda de pausa | El estado de `idle_timeout` no distingue ocioso de pausado. Una impresión pausada sola por el sensor de filamento perdía calentadores y, con el `M84`, la posición: el `RESUME` posterior imprime en el lugar equivocado |
| `[bltouch]` | `samples: 2`, tol. 0.0125 | `samples: 3`, tol. 0.025, `speed` / `lift_speed` | Con **dos** muestras la mediana *es* el promedio y no descarta el outlier: toda la protección quedaba en una tolerancia de 12.5 µm, que es más o menos la repetibilidad del propio CR-Touch. Con 81 puntos bastaba que uno fallara sus 4 intentos para abortar los otros ochenta. Y la subida del probe no mide nada: no tiene por qué ir a 5 mm/s |
| `[safe_z_home] z_hop_speed` | `5` | `10` | El suelto que quedó del `max_z_velocity` viejo. Se paga en cada `G28`, dos por impresión |
| Malla de cama | una sola, a 60 °C | `pla` / `petg` / `abs` | Aluminio con PEI cambia de forma decenas de micras entre 20 y 60, y otro tanto entre 60 y 100. El ABS —el material que más depende de la primera capa— imprimía sobre una malla medida 40 K más abajo. Son secciones `[bed_mesh NOMBRE]` que no existen en ningún include, así que `SAVE_CONFIG` las escribe sin conflicto, igual que `default` |
| `START_PRINT` | `M104` final antes del `M190` | `M190`, soak, y recién ahí el nozzle | El nozzle llegaba a temperatura en 30 s y se quedaba chorreando los 2-10 minutos que tarda la cama. No se ganaba tiempo, porque la cama siempre tarda más |
| `START_PRINT` | sin soak | `SOAK`, default 90 s | `M190` vuelve cuando el **termistor** toca el target, y está pegado abajo de la chapa. El `G28 Z` en caliente referenciaba sobre una cama a mitad de camino y después cargaba una malla que sí se midió en equilibrio |
| Purga | `Z0.28` fijo | `Z{LAYER}` | La línea existe para juzgar la primera capa y se imprimía un 40 % más alta que ella: daba una lectura optimista de lo único que sirve para diagnosticarla |
| `CALIBRAR_EXTRUSOR` | no existía | macro nuevo | `rotation_distance` sigue en `26.359`, el valor genérico de Klipper para esta placa. Max Flowrate y Flow Rate miden encima de él |
| `CALIBRAR_PID_NOZZLE` | sin nota | documenta el caso ABS | El PID medido con el fan al 100 % tiene ganancia alta, y el ABS imprime con el fan casi apagado. Es una elección —gana el PLA— y ahora está escrita como tal |
| `moonraker.conf` | fuera del repo | `versions/v3/`, y desplegado | Es la pieza que conecta las dos mitades: `[octoprint_compat]` es lo único que hace funcionar el `host_type: octoprint` del perfil de Orca, y `check` ahora valida ese par. El rol `klipper_config` lo despliega por un camino propio, porque reiniciar Moonraker no es lo mismo que reiniciar Klipper |

## Firmware del MCU

Sin cambios respecto de v2: el binario es el mismo (`klipper_v2.bin`, MD5
`e05ede5405515be4e456b3f76b1be553`). Se recompiló en junio de 2026 porque el host
de Klipper había subido a `v0.13.0-699-gc707dd192` mientras el MCU seguía en
`v0.12.0-178-g7e8c7f46`, y el desfasaje rompía la comunicación con un "Lost
communication with MCU".

### Placa

- MCU: STM32F401 (`stm32f401xc`), board Creality CR-FDM-v24S1
- Conexión host a MCU: chip CH340 (`1a86 USB Serial`) por USART1, 250000 baud
- Serial path: `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0`

### Build

Las opciones exactas de `make menuconfig` están en `firmware/build.config`. Las que
importan:

```
 Architecture         STMicroelectronics STM32
 Processor model      STM32F401
 Bootloader offset    64KiB bootloader   (CONFIG_STM32_FLASH_START_10000)
 Clock Reference      8 MHz crystal      (CONFIG_CLOCK_REF_FREQ=8000000)
 Comm interface       Serial on USART1 (PA10/PA9)
 Baud rate            250000
```

### Flasheo por microSD

1. Crear una carpeta `STM32F4_UPDATE` en una microSD en FAT32.
2. Copiar `firmware/klipper_v2.bin` adentro de esa carpeta.
3. Apagar la impresora, insertar la SD, encender. La pantalla NO debe mostrar el
   menú normal durante 10 a 30 segundos: eso significa que flasheó.
4. Apagar y **sacar la SD**, o vuelve a flashear en cada arranque.
5. Encender y correr `FIRMWARE_RESTART` en Mainsail. Verificar que `mcu_version`
   coincida con la versión del host.

## Cómo se despliega

No se copia a mano. Lo hace el rol `klipper_config` de
[nd.homelab](https://github.com/ndelucca/nd.homelab):

```sh
ansible-playbook playbooks/printers.yml -l ndelucca-raspberry-printer \
  -t klipper_config --check --diff     # ver el diff primero
ansible-playbook playbooks/printers.yml -l ndelucca-raspberry-printer \
  -t klipper_config
```

El rol aborta si hay una impresión en curso, hace backup, escribe los tres `.cfg`
en modo `0444`, reinicia Klipper y espera a que `/printer/info` devuelva
`state: ready`. Si el parser rechaza algo, falla mostrando el mensaje exacto.
