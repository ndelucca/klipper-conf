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
 macros.cfg           START_PRINT / END_PRINT / M0 / m300
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
