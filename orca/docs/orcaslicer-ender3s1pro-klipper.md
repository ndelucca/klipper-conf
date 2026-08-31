# OrcaSlicer - Ender 3 S1 Pro + Klipper

Configuración completa de OrcaSlicer para Ender 3 S1 Pro corriendo Klipper sobre
Raspberry Pi 3B+, con nozzle estándar de 0.4 mm y filamentos Printalot.

- **Fecha**: 2026-08-26
- **OrcaSlicer**: 2.4.2
- **Host de impresión**: Moonraker / Mainsail (la URL es local, ver `.printer-host`)
- **Perfiles**: 1 impresora, 5 procesos, 4 filamentos

---

## 1. Por qué la configuración anterior imprimía mal

El perfil viejo heredaba de `0.20mm Standard @MyKlipper`, que es el preset
genérico de Klipper que trae OrcaSlicer. Ese preset está pensado para una
CoreXY rápida con input shaper, no para una bed slinger.

```
                       Orca pedía        Klipper podía        Resultado
                       ----------        -------------        ---------
 Pared interior         200 mm/s          200 mm/s            ejecutado
 Relleno disperso       200 mm/s          200 mm/s            ejecutado
 Desplazamiento         350 mm/s          300 mm/s            recortado
 Aceleración general   5000 mm/s2        2000 mm/s2           RECORTADO
 Aceleración travel    7000 mm/s2        2000 mm/s2           RECORTADO
```

Las velocidades se ejecutaban tal cual, pero las aceleraciones las recortaba
Klipper. Eso ya explica la sensación de "va rapidísimo": la boquilla llegaba a
200 mm/s en tramos largos.

La mala calidad viene de otro lado, y son dos cosas que faltan en `printer.cfg`:

| Falta | Efecto a alta velocidad |
|---|---|
| `[input_shaper]` | Ringing / ghosting en cada esquina. Es lo que se ve como "eco" o fantasma de las aristas. |
| `pressure_advance` en `[extruder]` | Sub-extrusión al acelerar y blobs al frenar. Esquinas abultadas, paredes irregulares, seams marcados. |

Sin pressure advance, cualquier perfil rápido va a imprimir mal, porque el
extrusor no compensa el retraso de presión en el fundido. **Esta es la causa
principal de lo de ayer.**

Además había tres cosas menores mal:

- `printable_area` declaraba 250x250, pero el `position_max` de Y en Klipper es
  **235**. Había 15 mm de área fantasma.
- `machine_max_jerk_x/y` estaba en 20. En flavor Klipper eso se mapea a
  square corner velocity; el default de Klipper es 5. Un valor de 20 en una bed
  slinger genera golpes en cada cambio de dirección.
- `START_PRINT` hace `G28` pero nunca cargaba la malla de cama. Hay una malla
  6x6 guardada en el bloque `SAVE_CONFIG` de `printer.cfg` que **no se estaba
  usando en ninguna impresión**.

---

## 2. Hardware detectado

Leído directamente de `printer.cfg` y `macros.cfg` vía la API de Moonraker.

```
 Cinemática        cartesian (bed slinger)
 Área útil         X 220 x Y 220 x Z 270 mm  (la chapa; el carro llega a 250x235)
 Extrusor          Sprite Pro direct drive, gear ratio 42:12
 Hotend            bimetálico, max_temp 300
 Cama              max_temp 110
 Probe             BLTouch, offset X -48 / Y 0, malla 6x6 con fade hasta Z=10
 Ventilador        uno solo de capa (4020 stock), sin ventilador auxiliar
 Sensor            filament runout en e0_sensor, pausa automática

 [printer]
   max_velocity        300 mm/s
   max_accel          2000 mm/s2      <- techo real de todo el perfil
   max_z_velocity       10 mm/s
   max_z_accel         200 mm/s2

 [input_shaper]        NO CONFIGURADO
 pressure_advance      lo pone START_PRINT segun el material
```

El módulo `[exclude_object]` está presente y el perfil lo aprovecha.
`[gcode_arcs]` también, y desde `versions/v3` declara `resolution: 0.2`, que es lo
que hace seguro el arc fitting. Con el default de 1 mm quedaban facetas visibles
en los radios chicos.

Estas dependencias ya no se controlan a ojo: las valida
`python orca/orca.py check` contra `versions/<CURRENT>/`, y CI las corre en cada
push.

---

## 3. Archivos

Todo vive en `%APPDATA%\OrcaSlicer\user\default\`.

```
 <data>/                                 %APPDATA%\OrcaSlicer en Windows
 |
 +-- OrcaSlicer.conf                      seleccion recordada + checksum MD5
 |
 +-- user\default\
     |
     +-- machine\
     |   +-- EnderS1ProKlipper.json       LA impresora
     |   +-- EnderS1ProKlipper.info
     |
     +-- process\
     |   +-- 0.12mm Fine @EnderS1Pro.json
     |   +-- 0.20mm Standard @EnderS1Pro.json    <- DEFAULT
     |   +-- 0.20mm Strong @EnderS1Pro.json
     |   +-- 0.28mm Draft @EnderS1Pro.json
     |   +-- 0.20mm ABS @EnderS1Pro.json
     |   +-- (un .info por cada uno)
     |
     +-- filament\
         +-- Printalot PLA @EnderS1Pro.json
         +-- Printalot PETG @EnderS1Pro.json
         +-- Printalot ABS @EnderS1Pro.json
         +-- Printalot TPU Flex @EnderS1Pro.json
         +-- (un .info por cada uno)
```

Cada `.json` es el preset y cada `.info` es el metadato de sincronización que
Orca usa para saber de qué preset de sistema deriva.

### Cadena de herencia

Los perfiles no son autocontenidos: heredan de los presets de fábrica y pisan
solo lo que hace falta. Eso los mantiene compatibles con futuras versiones de
OrcaSlicer.

```
 EnderS1ProKlipper
   <- MyKlipper 0.4 nozzle  <- fdm_klipper_common  <- fdm_machine_common

 0.20mm Standard @EnderS1Pro
   <- 0.20mm Standard @MyKlipper  <- fdm_process_klipper_common  <- fdm_process_common

 Printalot PLA @EnderS1Pro
   <- Generic PLA @System  <- fdm_filament_pla  <- fdm_filament_common
```

### Limpieza hecha

- Se eliminó el bundle importado `user\default\_local\49ea5240-...\`, que
  contenía el filamento suelto `Printalot PLA @Klipper`.
- Los filamentos genéricos de sistema visibles bajaron de 10 a 4 (se dejaron
  solo PLA, PETG, ABS y TPU, que son los padres de los perfiles Printalot).
- Los 5 procesos y los 4 filamentos declaran `compatible_printers:
  ["EnderS1ProKlipper"]`, así que **no aparecen si seleccionás otra impresora**.

### Repositorio

Toda esta configuración vive versionada en `~/nd.printer`, con dos capas
sincronizadas:

```
 orcakit/profiles.py        presets/                  OrcaSlicer
 ---------------            --------                  ----------
 definición en Python  -->  snapshot JSON        -->  instalación
 (fuente de verdad)         (lo que se versiona)      (tu máquina)

       orca.py build              orca.py install
                                  orca.py verify   <---- compara estas dos
```

`orcakit/profiles.py` es la fuente de verdad. Para cambiar algo de forma
permanente: editar ahí, correr `python orca.py build`, y después
`python orca.py install` con **OrcaSlicer cerrado**.

No editar los perfiles desde la interfaz de OrcaSlicer: se pierden en el
próximo `install` y el repo deja de reflejar la realidad. Ver el `README.md`
del repo para el detalle de los comandos.

---

## 4. Perfil de impresora: `EnderS1ProKlipper`

### Volumen y hardware

| Ajuste | Valor | Por qué |
|---|---|---|
| Área imprimible | 220 x 220 mm | Es el área útil de la **chapa**, no el recorrido del carro. `position_max` (250 x 235) dice hasta dónde llega el carro, y el carro llega más lejos que el plato: declarar 250 dejaba a Orca poner una pieza 30 mm al aire. `check` valida que el área declarada *entre* en el recorrido, no que sea igual |
| Altura | 270 mm | |
| Altura de capa | 0.08 a 0.32 mm | 0.32 = 80% del nozzle, el máximo sano para 0.4 |
| Tipo de extrusor | Direct Drive | |
| Tipo de nozzle | brass | El de fábrica |
| Estructura | i3 | Bed slinger |

### Límites de máquina

Son un espejo exacto de `printer.cfg`. **No mandan sobre la impresora**: sirven
para que la estimación de tiempo de Orca sea real. Antes decían 3000 de
aceleración cuando Klipper hacía 2000, y por eso el tiempo estimado mentía.

```
 machine_max_speed_x / y            300 mm/s
 machine_max_speed_z                 10 mm/s
 machine_max_acceleration_x / y    3000 mm/s2   <- techo MECANICO, no de calidad
 machine_max_acceleration_z         200 mm/s2
 machine_max_jerk_x / y               5      (= square corner velocity default de Klipper)
```

**`max_accel` no es el presupuesto de ringing.** Son dos cosas distintas y
estuvieron confundidas en un solo número:

- **Techo mecánico** (`[printer] max_accel`, hoy 3000): hasta dónde puede
  acelerar la máquina sin perder pasos.
- **Presupuesto de ringing** (2000, y 700 en la pared exterior): cuánta
  aceleración tolera la superficie *que se ve*.

El travel solo debe respetar el primero: el ringing de un desplazamiento por el
aire no deja marca en la pieza. Mientras los dos estuvieron atados en 2000, el
travel pagaba una restricción de calidad superficial que no le correspondía —
llegar a los 250 mm/s de `travel_speed` exigía **15.6 mm** de recorrido, y casi
ningún travel de una pieza real es tan largo. Con 3000 son 10.4 mm.

Ninguna aceleración de impresión se movió al hacer el cambio. `orca.py check`
valida las dos reglas por separado: la sección 2 compara todas las
aceleraciones contra el techo mecánico, y la sección 6 compara **solo las de
impresión** contra el techo de ringing.

`emit_machine_limits_to_gcode` está en **0**: Orca no emite el bloque de
`SET_VELOCITY_LIMIT` al inicio. Los límites los pone `printer.cfg` y punto, que
es la forma correcta de trabajar con Klipper. Las aceleraciones por feature sí
se emiten como `M204`, que Klipper acepta sin problema.

### Retracción (Sprite Pro direct drive)

| Ajuste | Valor |
|---|---|
| Longitud | 0.6 mm |
| Velocidad de retracción | 35 mm/s |
| Velocidad de reinserción | 30 mm/s |
| Desplazamiento mínimo | 2 mm |
| Z hop | 0.3 mm, tipo Auto Lift. 0.2 era menos despeje que un blob o que un borde levantado, y `slowdown_for_curled_perimeters` ya asume que los hay |
| Wipe | activado, 1 mm, sin retracción previa |

0.6 mm es lo correcto para un direct drive. El perfil viejo tenía 0.5, que
está en el límite bajo y deja stringing.

El desplazamiento mínimo estuvo en 1 mm, que hacía retraer en prácticamente
cada travel. Cada par retracción/reposición mete un transitorio de presión; con
`wipe` y `reduce_infill_retraction` queda tapado casi siempre, pero a 1 mm son
cientos de oportunidades por capa de que no lo tape.

### G-code

```gcode
; machine_start_gcode
START_PRINT BED_TEMP=[bed_temperature_initial_layer_single] EXTRUDER_TEMP=[nozzle_temperature_initial_layer] MATERIAL=[filament_type] LAYER=[initial_layer_print_height]

; layer_change_gcode
;AFTER_LAYER_CHANGE
;[layer_z]
G92 E0

; machine_end_gcode
END_PRINT
```

Dos cosas importantes acá:

**`MATERIAL=[filament_type]`** es lo que le permite a Klipper poner el pressure
advance por su cuenta. El macro tiene la tabla por material (`variable_pa`) y el
laminador solo anuncia cuál está cargado, así que cualquier g-code hereda el PA
correcto aunque no lo haya generado OrcaSlicer.

**La carga de la malla ya no está acá.** Antes el start gcode hacía
`BED_MESH_PROFILE LOAD=default`, porque `START_PRINT` hace `G28` y nunca volvía a
cargarla. Eso ahora lo hace el propio macro, que es donde corresponde: la malla es
de la máquina, no del laminador. `orca.py check` falla si nadie la carga.

**Qué hace `START_PRINT` del lado de la máquina.** El contrato con el laminador
son tres parámetros, pero del otro lado el macro hace bastante más:

```
 chequeo del sensor de filamento             lo primero de todo: sin filamento
                                             no se enciende nada. Antes se
                                             descubría en la primera extrusión
                                             de la purga, seis minutos después
 M107 / CLEAR_PAUSE / M220 / M221 /          higiene: todo lo que sobrevive de
 SET_GCODE_OFFSET X Y Z /                    una impresión a la siguiente y que
 SET_VELOCITY_LIMIT /                        nadie limpia. El fan soplando, el
 SET_FILAMENT_SENSOR ENABLE=1                estado de pausa, los sliders de
                                             velocidad y flujo de Mainsail, el
                                             babystep de la anterior, un límite
                                             de velocidad pisado a mano, y el
                                             sensor de filamento que apagaste
                                             una vez y quedó apagado
 M104 S150 / M140                            precalentamiento EN PARALELO, sin
                                             esperarlo. Acá hubo un
                                             TEMPERATURE_WAIT MINIMUM=150 que
                                             no hacía nada: no hay extrusión
                                             hasta el M190, el G28 palpa con el
                                             BLTouch, y el G28 Z en caliente
                                             descarta el valor de este homing
 G28 / G1 Z20                                homing (Z todavía en frío) y
                                             parqueo bajo, porque el G28 Z de
                                             abajo baja desde acá
 M190                                        LA CAMA PRIMERO, SOLA. Ver abajo
 G4 <SOAK-45> / M104 final / G4 45           soak de cama, PARTIDO: el nozzle
                                             sube durante la cola. Ver abajo
 M109                                        vuelve enseguida
 G28 Z                                       RE-HOME EN CALIENTE. Ver abajo
 BED_MESH_PROFILE LOAD=<pla|petg|abs>        la malla que corresponde a la
                                             temperatura de cama anunciada
 SET_PRESSURE_ADVANCE                        según el MATERIAL anunciado
 G1 Z10 / G1 X8 Y10                          reposicionar ANTES de bajar
 purga en X=8, a Z=<LAYER>                   borde de la chapa, dentro de la
                                             malla, a la altura de la primera
                                             capa del proceso y con el caudal
                                             que corresponde a esa altura
 tirón + hop                                 corta el hilo antes de devolverle
                                             el control al laminador
```

**La cama primero, sola.** El `M104` al valor final estaba antes del `M190`, y
eso dejaba el nozzle a 215 —o a 255 en ABS— chorreando durante toda la subida de
la cama: 2-3 minutos a 60 °C, 6-10 a 100. Se pagaba en el bulbo que la purga
tiene que barrer, en el goteo sobre la chapa, y en minutos de PETG o ABS
cocinándose en la zona de fusión. Y no se ganaba tiempo, porque la cama siempre
tarda más que el nozzle: adelantar el `M104` ahorraba los ~30 s que tarda el
bloque en subir de 150 a 215.

**El soak.** `M190` vuelve cuando el **termistor** toca el target, y ese
termistor está pegado abajo de la chapa: es exactamente el motivo por el que el
procedimiento de `BED_MESH_CALIBRATE` exige esperar 10 minutos antes de palpar.
Sin la espera, el `G28 Z` de abajo referencia el Z sobre una cama a mitad de
camino y después carga una malla que **sí** se midió en equilibrio: las dos
referencias del Z no corresponden al mismo estado térmico del aluminio.

El `SOAK` **no** lo manda el laminador. Sale de la misma escalera de `BED_TEMP`
que elige la malla —90 s para PLA, 150 para PETG, 420 para ABS— porque es la
misma pregunta: qué régimen térmico es este. Estuvo clavado en `SOAK=90` desde
Orca mientras la malla se elegía sola, o sea dos respuestas a una sola pregunta,
y la clavada era la equivocada: el ABS hacía 90 s de soak y después cargaba la
malla medida en equilibrio a 100 °C. El macro sigue leyendo `SOAK=` como
override si hace falta para un caso puntual.

El dwell va **partido en dos**, con el `M104` al valor final metido en los
últimos 45 s. El argumento de "la cama siempre tarda más" vale para la rampa de
la cama, no para el soak: ahí la cama ya está en target y lo único que pasa es
que el aluminio se equaliza, así que los ~35 s de 150→215 se pagaban enteros y
en serie.

**La altura de la purga.** Estuvo fija en `Z0.28` mientras los procesos imprimen
la primera capa a 0.20 (0.25 en Draft). Esa línea existe para juzgar la primera
capa, y a 0.28 salía redondeada aunque el `z_offset` estuviera 0.05 mm alto: daba
una lectura optimista justo de lo que sirve para diagnosticar. Ahora la altura
llega por parámetro, y `check` valida que el laminador la mande.

**Y el caudal, que es la otra mitad del mismo argumento.** Con un `E10` fijo el
área depositada es constante, así que el ancho real de la línea depende de la
altura: 0.97 mm a 0.20 y 1.57 mm a 0.12, contra los ~0.42 de una línea real. Una
línea sobre-extruida al 230 % se ve bien aunque el `z_offset` esté alto, porque
el material de sobra tapa la falta de aplastamiento: el mismo defecto de lectura
que el 0.28, por el otro eje, y peor justo en el perfil Fine. Ahora el `E` sale
de `LAYER` para un ancho objetivo de 0.6 mm, y las dos pasadas quedan tangentes
en vez de una encima de la otra.

El `G28 Z` en caliente es el que más rinde de esa lista. El primer `G28` ocurre
con la cama a temperatura ambiente y el nozzle a 150; para cuando se imprime la
primera capa la cama subió hasta 100 °C y el bloque otros 60, y todo eso dilata
unas décimas. Es la causa clásica de que el `z_offset` sirva para PLA y no para
ABS. Cae además en el mismo punto que el `zero_reference_position` de
`[bed_mesh]` (110,110 en coordenadas de probe), así que la referencia del Z y el
ancla de la malla son físicamente el mismo lugar.

El reposicionamiento que va justo antes de la purga no es decorativo. `G28 Z`
pasa por `[safe_z_home]`, que manda el carro a `home_xy_position` (158,110) para
palpar y **no vuelve solo** (`move_to_previous` es `false` por defecto). Sin ese
`G1 X8 Y10`, el descenso a Z=0.28 ocurre en el medio de la cama y la primera
línea de purga cruza la placa en diagonal, 136 mm, con el nozzle apoyado.

La purga vive en **X=8**. Estuvo en X=2, fuera de la malla: esos 130 mm de línea
salían con el Z **extrapolado**, o sea que la línea que existe para juzgar la
primera capa era justo donde menos se sabía. Se movió a X=25 para meterla dentro
de la malla, pero eso se comía 25 mm del borde izquierdo de la bandeja. Bajando
`mesh_min` a X=5 desaparece el dilema: en X=8 la purga cae sobre dato medido y
sobre el borde. `mesh_min` estaba en 20 por copiar la posición del primer
tornillo de nivelación, no por una restricción física — hacia la izquierda el
probe llega hasta X=-58, así que palpar X=5 sólo exige el nozzle en X=53.

El borde **derecho** es otra historia y no tiene solución: con `x_offset: -48`,
palpar X=200 ya exige el nozzle en X=248 contra un `position_max` de 250. Los
últimos 20 mm de la bandeja son inalcanzables para el probe, así que van con Z
extrapolado por construcción. Es una consecuencia del toolhead, no un valor a
ajustar.

**`G92 E0`** en el cambio de capa es obligatorio: el perfil usa extrusión
relativa (`M83`, que tu macro ya setea) y sin ese reset se pierde precisión de
punto flotante en el acumulador de E en impresiones largas. OrcaSlicer
directamente rechaza el perfil si falta.

### Previews en Mainsail

```
 thumbnails          32x32 y 300x300
 thumbnails_format   PNG
```

Ahora los `.gcode` llevan miniatura embebida y Mainsail te muestra la pieza en
la cola de impresión en vez de un ícono genérico.

---

## 5. Los 5 procesos

La idea es que el **proceso define la geometría y la ambición de velocidad**, y
el **filamento pone el techo de caudal**. Casi no hay procesos por material:
eso lo resuelve solo Orca (ver sección 7). La única excepción es el ABS, y más
abajo está el porqué.

| | Fine | **Standard** | Strong | Draft | ABS |
|---|---|---|---|---|---|
| Altura de capa | 0.12 | **0.20** | 0.20 | 0.28 | 0.20 |
| Perímetros | 2 | **3** | 4 | 2 | 3 |
| Relleno | 15% gyroid | **15% gyroid** | 40% cubic | 10% gyroid | 15% gyroid |
| Techo superior | 0.84 mm | **0.80 mm** | 1.00 mm | 0.84 mm | 0.80 mm |
| Base | 0.60 mm | **0.60 mm** | 0.80 mm | 0.56 mm | 0.60 mm |
| Pared exterior | 45 mm/s | **50 mm/s** | 50 mm/s | 50 mm/s | 50 mm/s |
| Pared interior | 120 mm/s | **110 mm/s** | 100 mm/s | 80 mm/s | 110 mm/s |
| Relleno disperso | 140 mm/s | **110 mm/s** | 110 mm/s | 75 mm/s | 110 mm/s |
| Relleno sólido | 130 mm/s | **115 mm/s** | 110 mm/s | 80 mm/s | 115 mm/s |
| Superficie superior | 40 mm/s | **45 mm/s** | 45 mm/s | 45 mm/s | 45 mm/s |
| Caudal pedido | 7.6 mm3/s | **9.9 mm3/s** | 9.9 mm3/s | 10.8 mm3/s | 9.9 mm3/s |
| Costura scarf | sí | **sí** | sí | no | sí |
| Planchado | sí | **sí** | no | no | sí |
| Orden de paredes | normal | **normal** | inner-outer-inner | normal | normal |
| Brim | auto | **auto** | auto | auto | outer_only 8 mm |
| Draft shield | no | **no** | no | no | sí |

**Para qué es cada uno:**

- **0.12mm Fine** - miniaturas, piezas con detalle fino, texto en relieve.
  Limitado por aceleración, no por caudal, así que las velocidades son altas sin
  costo de calidad.
- **0.20mm Standard** - el de todos los días. Es el default de la impresora.
- **0.20mm Strong** - piezas funcionales que tienen que aguantar. 4 perímetros y
  40% de relleno cubic (isotrópico, sin cruces de boquilla como el grid a
  densidad alta). Más lento a propósito, para que las capas peguen mejor.
- **0.28mm Draft** - prototipos y piezas grandes. Acá el límite es el caudal del
  hotend, no la velocidad: a 0.28 de capa cada milímetro de recorrido mueve
  mucho más plástico, así que las velocidades bajan aunque el tiempo total
  mejore mucho.
- **0.20mm ABS** - Standard con lo que el ABS necesita para sobrevivir a una
  impresora **sin encerramiento**. Ver abajo.

### Por qué el ABS sí necesita su propio proceso

Es la excepción a la regla de "el filamento resuelve el material solo", y no
por gusto: **`brim_type` y `draft_shield` son claves de proceso, y en
OrcaSlicer un filamento no puede pisar una clave de proceso.**

Las notas del filamento ABS decían *"Obligatorio en el proceso: Brim outer_only
8mm"* y *"Recomendado: Draft shield"*. O sea que la fuente de verdad de este
repo documentaba un paso manual en la UI, sin verificación posible, para el
único material donde los defaults del proceso están realmente mal. Un quinto
proceso lo devuelve al lado del repo que `check` mira.

| Qué cambia | Valor | Por qué |
|---|---|---|
| `brim_type` | outer_only | En ABS el brim no es una ayuda marginal de adherencia: es lo que sostiene las esquinas contra el warp. Solo por fuera, porque uno interno no aporta nada ahí y complica despegar la pieza |
| `brim_width` | 8 mm | |
| `draft_shield` | enabled | La pared de sacrificio alrededor de la pieza. No calienta el aire, pero corta la corriente — y sin encerramiento, la mayor parte del gradiente que delamina viene de aire moviéndose, no de temperatura ambiente baja |

**Lo que deliberadamente NO cambia: la velocidad y la aceleración.** Suena
razonable imprimir ABS más lento "para que no warpee", y es al revés. Sin caja,
el modo de falla dominante es la **delaminación**: la capa de abajo se enfría de
más antes de que llegue la de arriba. Ir más lento le da *más* tiempo para
enfriarse, no menos. Es el mismo razonamiento por el que el filamento va a 255
y no a 245. Bajar la aceleración solo ayudaría si la pieza se despegara de la
cama por inercia, y para eso está el brim.

### Aceleraciones (idénticas en todos)

```
 --- presupuesto de ringing: deposita plastico, se ve ---
 Pared exterior             700 mm/s2      <- lo que se ve, lo mas suave posible
 Superficie superior        700 mm/s2
 Pared interior            2000 mm/s2
 Relleno sólido            2000 mm/s2
 General                   2000 mm/s2
 Primera capa               500 mm/s2
 Puentes                     50%  (= 1000)

 --- techo mecanico: por el aire, no deja marca ---
 Desplazamiento            3000 mm/s2      <- = [printer] max_accel
 Desplazamiento 1a capa    1000 mm/s2
```

El corte entre los dos bloques es el que valida `orca.py check`: la sección 6
compara **solo el primero** contra el techo de ringing de 2000. Ver "Límites de
máquina" en la sección 4.

`default_jerk` está en 0 a propósito: eso hace que Orca no toque el square
corner velocity y lo maneje Klipper con su default de 5.

Fine usa 600 mm/s2 en pared exterior y superficie superior en vez de 700,
porque a 0.12 de capa el ringing se nota más. Draft va al revés: 1000, porque
prioriza tiempo y esas piezas no se miran de cerca.

Los 700 y los 2000 son, hoy, una intuición y no una medición. La amplitud
residual de vibración va como `a / (2*pi*f)^2`, o sea que **el número que falta
es la frecuencia de resonancia de cada eje**, no la aceleración. En micras:

```
  f (Hz)     a=700   a=1000   a=2000   a=4000
    25        28       41       81      162
    40        11       16       32       63
    60         5        7       14       28
```

El umbral de lo que se ve a contraluz anda por las 20-30 micras. Si X resuena a
40-60 Hz (lo típico de un carro liviano), 700 está dejando velocidad sobre la
mesa; si Y, que mueve la cama con la pieza encima, resuena a 25 Hz, 700 ya está
al filo. **Las dos cosas pueden ser ciertas a la vez, en ejes distintos**, y hoy
hay un solo número para los dos. La torre de ringing (sección 8) da `f` por eje
en una impresión de 20 minutos, sin comprar nada.

### Ajustes de calidad activados

| Ajuste | Valor | Qué hace |
|---|---|---|
| `wall_generator` | arachne | Ancho de pared variable. Resuelve mucho mejor paredes finas y detalles chicos que el modo clásico |
| `precise_outer_wall` | sí | Precisión dimensional: la pieza sale con la medida real del modelo |
| `only_one_wall_top` | sí | Un solo perímetro en la última capa, deja techos más limpios |
| `ensure_vertical_shell_thickness` | ensure_moderate | Evita agujeros en paredes casi verticales sin inflar el tiempo |
| `seam_position` | aligned | Costura alineada en una columna |
| `seam_slope_type` | external | **Scarf joint**: reparte el solape de la costura en una rampa de varios milímetros en vez de cortar y volver a arrancar en el mismo punto, que es lo que deja el blob. Activo en Fine, Standard y Strong; en Draft no, porque esas piezas no se miran de cerca |
| `seam_slope_conditional` | sí | Aplica el scarf solo donde la pared es lo bastante lisa (ángulo > 155°). En una esquina viva el scarf se ve peor que la costura normal, así que ahí se abstiene |
| `wall_sequence` | inner-outer-inner (Standard, Strong y ABS) | Deposita la pared exterior apoyada contra material ya sólido de los dos lados. **Necesita 3 paredes o más para significar algo**: con `wall_loops: 2` (Fine y Draft) no hay tercera pared y el modo degenera al orden normal. Standard subió a 3 perímetros justamente por esto: con 2, la pared exterior se depositaba contra relleno al 15 %, o sea contra aire la mayor parte del recorrido |
| `staggered_inner_seams` | sí | Escalona las costuras internas, no se apilan todas |
| `enable_arc_fitting` | **sí** | Depende de que `limits.cfg` declare `[gcode_arcs] resolution: 0.2`. La sagita de un segmento de largo L sobre un radio R es `L²/(8R)`, así que en el peor caso realista (un agujero de 2 mm, R=1) el default de Klipper de 1 mm deja 0.125 mm de faceta, 0.2 deja 0.005 mm y 0.1 deja 0.0013 mm. 0.1 estuvo puesto un tiempo y era ~80 veces más fino de lo que esta máquina posiciona, a cambio de 1100 segmentos por segundo que paga el planificador de Klipper en una Pi 3B+. `orca.py check` valida ese par, y 0.2 es justo el límite que acepta |
| `exclude_object` | sí | Tu Klipper tiene `[exclude_object]`. Podés cancelar una pieza sola desde Mainsail sin abortar el plato |
| `elefant_foot_compensation` | 0.15 mm | Compensa el aplastado de la primera capa |
| `slowdown_for_curled_perimeters` | sí | Frena donde detecta perímetros que se levantan |
| `ironing_type` | top (Fine y Standard; **no** en ABS) | **Planchado**: `monotonicline` ordena las pasadas de la cara superior y `only_one_wall_top` le saca la costura del medio, pero entre línea y línea sigue quedando el valle del propio cordón. El planchado lo rellena pasando el nozzle casi vacío por encima (flow 10 %, spacing 0.15, 30 mm/s). `top` y no `topmost` para planchar toda cara superior expuesta, no solo la última capa; `all solid` plancharía también las sólidas internas, que nadie ve. Cuesta tiempo **solo** en caras superiores. En Strong y Draft no va, por el mismo criterio que el scarf joint. Y **no** en ABS, aunque herede de Standard: con el ventilador entre 0 y 15 % la cara superior no está rígida cuando el nozzle vuelve a pasarle por encima, así que arrastra material en vez de fundir el valle |

### Anchos de línea

```
 General                0.42 mm       105% del nozzle
 Pared exterior         0.42 mm
 Pared interior         0.45 mm
 Relleno sólido         0.42 mm
 Relleno disperso       0.45 mm
 Superficie superior    0.40 mm       más fino = mejor terminación
 Primera capa           0.50 mm       más ancho = más adherencia
 Soportes               0.36 mm       más fino = se despegan más fácil
```

Draft usa anchos más gruesos (hasta 0.50) porque a esa altura de capa conviene
mover más material por pasada.

### Skirt desactivado

`skirt_loops = 0` porque tu macro `START_PRINT` ya hace dos líneas de purga
completas a lo largo de la cama. El skirt sería redundante y suma tiempo.

El proceso ABS es la excepción: ahí `draft_shield = enabled` levanta una pared
de sacrificio alrededor de la pieza, que no es un skirt de purga sino un
cortavientos. Ver sección 5.

---

## 6. Los 4 filamentos

| | PLA | PETG | ABS | TPU Flex |
|---|---|---|---|---|
| Nozzle | 215 | 240 | 255 | 230 |
| Primera capa | 220 | 245 | 260 | 230 |
| Cama | 60 | 70 | 100 | 45 |
| Rango sugerido | 190-230 | 220-260 | 230-270 | 210-240 |
| Caudal máximo | 10 mm3/s | 9 mm3/s | 10 mm3/s | 3.5 mm3/s |
| Flow ratio | 0.98 | 0.95 | 0.98 | 1.00 |
| Ventilador min/max | 100 / 100 | 40 / 60 | 0 / 15 | 50 / 80 |
| Capas sin ventilador | 1 | 2 | 3 | 1 |
| Retracción | 0.6 (impresora) | 0.8 | 0.6 | 0.4 |
| Densidad | 1.24 | 1.27 | 1.04 | 1.21 |
| Contracción | - | - | 100.6% | - |

Las temperaturas de cama están seteadas **iguales en todos los tipos de placa**
(Cool, Engineering, High Temp, Textured, Supertack). Así el perfil funciona sin
importar qué "Bed type" tengas seleccionado en la UI y no hay forma de que salga
una primera capa con la cama a otra temperatura por error.

Cada filamento tiene notas cargadas en el campo **Notes** de OrcaSlicer, visibles
desde la propia interfaz.

### Cosas específicas por material

**PLA** - No tiene mucho misterio. La chapa PEI del lado liso a 60 grados agarra
bien. Limpiala con alcohol isopropílico, no con agua y detergente.

El piso de tiempo por capa (`slow_down_layer_time`) es de **8 segundos**, no de
6. El 4020 radial de fábrica es flojo, y en una capa de 1 a 2 segundos —un cubo
de calibración, la punta de un cono, un detalle fino— 6 segundos de piso no
alcanzan a solidificar antes de que vuelva el nozzle: la punta queda blanda y
traslúcida. El costo está acotado a las capas que **ya** son diminutas, así que
en tiempo absoluto es casi nada.

> **Sobre el caudal de 10 mm3/s.** Es un valor **estimado, no medido**, y está
> puesto conservador a propósito. El techo de caudal no lo pone el `max_temp: 300`
> del hotend: eso es un límite de seguridad de Klipper (lo que habilita ABS y PC),
> no cuánto plástico puede fundir el bloque por segundo. Lo que manda ahí es la
> potencia del calentador y el largo de la zona de fusión, que en el Sprite stock
> es corta. Y el PLA tiene además un techo propio del material: arriba de ~230 °C
> se degrada dentro del hotend, así que subir temperatura para ganar caudal tiene
> un límite bajo.
>
> Antes esto decía 11 con el nozzle a 210, y el proceso Standard pedía 10.8: el
> 98 % de un número no medido. El mecanismo de auto-freno de la sección 7 **solo
> protege si el techo declarado es honesto**; si el hotend real daba 9, Orca no
> frenaba nada y el relleno sub-extruía en silencio. Con 10 el freno actúa y el
> perfil queda seguro dé lo que dé la medición. Cuando corras
> Calibration -> Max Flowrate, subí el valor al medido.

**PETG - leer esto antes de imprimir**

> Estás usando la chapa PEI **del lado liso**. El PETG se suelda químicamente al
> PEI liso y al despegar la pieza arranca pedazos de la lámina. Es un problema
> conocido y arruina la chapa.
>
> Usá **siempre stick de pegamento** (barra escolar) como separador, y despegá la
> pieza recién cuando la cama esté fría.
>
> La cama está a 70 a propósito. No la subas: cuanto más caliente, más se suelda.
> Si te despega en una esquina, sumá brim antes de subir temperatura.

**ABS - sin encerramiento**

El ventilador está prácticamente apagado (0 a 15%) porque sin caja el ABS
delamina si lo enfriás. Y el nozzle está a **255**, alto a propósito: sin
encerramiento el modo de falla dominante no es el warp de la cama (eso lo tapa
el brim) sino la **delaminación**, la capa de abajo se enfría de más antes de
que llegue la de arriba y la pieza se abre por una línea horizontal. Más calor
por capa compensa el que se pierde al ambiente, y es la contramedida estándar.
El material aguanta hasta ~270 y el hotend hasta 300, así que 255 sobra de
margen. Ese margen se gasta entero en unión de capas: el techo de caudal se
queda en 10.

> A 0-15 % de PWM un ventilador 4020 arrancando desde parado **no gira**: queda
> energizado, zumbando, sin mover aire. Por eso `[fan]` en `hardware.cfg` tiene
> `kick_start_time: 0.5` (lo larga a 100 % medio segundo y recién ahí baja al
> duty pedido) y `off_below: 0.10` (apaga limpio en vez de dejarlo trabado).

Para que funcione:

```
 En el laminador:
   Proceso  ->  0.20mm ABS @EnderS1Pro

 En el ambiente:
   Cerrar puertas y ventanas. Cero corriente de aire.
   Ventilar la habitación DESPUÉS de imprimir: el ABS emite VOC.
```

Elegir el proceso es todo lo que hay que hacer. Esto **fue** un paso manual:
había que acordarse de poner brim `outer_only` de 8 mm y draft shield en la UI
antes de cada laminado, porque son claves de proceso y un filamento no las puede
pisar. Ahora viven en `0.20mm ABS @EnderS1Pro` y `check` las mira. Ver la
sección 5 para el porqué, incluido qué se dejó deliberadamente igual que en
Standard (la velocidad y la aceleración: ir más lento **empeora** la
delaminación, no la mejora).

Con la impresora al aire, piezas de más de ~100 mm van a warpear igual. Es
limitación física, no del perfil. Si vas a hacer ABS seguido, una caja de
cartón forrada con aislante ya cambia mucho las cosas.

La compensación de contracción está en 100.6%: Orca agranda la pieza ese
porcentaje para que al enfriarse quede con la medida correcta.

**TPU Flex**

El caudal máximo de 3.5 mm3/s es el que gobierna todo. No necesitás un proceso
aparte: Orca frena solo todas las velocidades (ver sección siguiente).

Configuración específica para que no se trabe el Sprite:

```
 Retracción            0.4 mm a 20 mm/s        mínima
 Z hop                 desactivado
 Retraer al cambiar de capa   no
 Wipe                  desactivado
 Desplazamiento mínimo para retraer   3 mm
```

Cargá el filamento a mano, despacio, con el extrusor ya caliente. El TPU se
dobla dentro del engranaje si lo empujás con el motor.

---

## 7. Cómo Orca frena solo (el mecanismo clave)

Este es el motivo por el que un puñado de procesos alcanza para 4 materiales
muy distintos, y por el que solo el ABS necesitó uno propio (y no por caudal,
sino por brim y draft shield: ver sección 5).

Cada filamento declara `filament_max_volumetric_speed`, que es cuántos mm3 de
plástico por segundo puede fundir el hotend con ese material. Al laminar, Orca
calcula el caudal de cada movimiento:

```
 caudal (mm3/s) = altura de capa x ancho de línea x velocidad (mm/s)
```

Si el resultado supera el techo del filamento, **baja la velocidad de ese
movimiento** hasta que entre. No lo hace globalmente: lo hace feature por
feature.

Ejemplo real con el proceso Standard:

```
                              PLA (10)      PETG (9)      TPU (3.5)
                              --------      --------      ---------
 Relleno disperso 110 mm/s      9.9 ok      frena a 100    frena a 39
 Pared interior   110 mm/s      9.9 ok      frena a 100    frena a 39
 Pared exterior    50 mm/s      4.2 ok       4.2 ok        frena a 42
```

Standard es el único proceso cuyo principio de diseño es **no tocar nunca el
techo del PLA**: corre a la velocidad nominal y el auto-freno queda de red para
los otros materiales.

Llegar ahí costó dos correcciones. El techo del PLA decía 11, un número que
nunca se midió, y Standard pedía 10.8 contra él: el 98 %, sin tocar el límite.
Sonaba elegante y era frágil, porque **el auto-freno solo protege si el número
que lo dispara es honesto** — con un techo optimista Orca no frena, y el relleno
sub-extruye sin dar síntoma. Bajado el techo a 10 (conservador), esos nominales
de 120 pasaban a ejecutarse a 111: el archivo decía una cosa y la impresora
hacía otra. Por eso hoy son 110 y 115, calculados para dar 9.90 y 9.66.

Cuando corras Calibration -> Max Flowrate y tengas el número real, esos tres
nominales suben con `filament_max_volumetric_speed`.

Contraste completo de los procesos contra los materiales:

```
 proceso            PLA(10)   PETG(9)   ABS(10)   TPU(3.5)   pico
 -------------------------------------------------------------------
 0.12mm Fine           ok        ok        ok      frena     7.6
 0.20mm Standard       ok      frena       ok      frena     9.9
 0.20mm Strong         ok      frena       ok      frena     9.9
 0.28mm Draft        frena     frena     frena     frena    10.8
 0.20mm ABS            ok      frena       ok      frena     9.9
```

"frena" no es un error: es el sistema funcionando. Significa que el proceso pide
más caudal del que ese material tolera y Orca lo ajusta solo.

---

## 8. Lo que falta medir, en orden

Esta configuración está razonada de punta a punta, pero descansa sobre
**constantes genéricas, no sobre mediciones de esta máquina**: el caudal máximo,
el flow ratio, el pressure advance, la compensación de agujeros y la frecuencia
de resonancia de cada eje. Todos están documentados como suposiciones donde
viven, y esta es la lista para convertirlos en datos.

El orden importa: cada paso asume que el anterior está hecho. Nivelar después de
calibrar el flujo significa recalibrar el flujo.

### Fase A - la máquina física (no cuesta un peso, no toca el firmware)

```
 A1. NIVELACION MECANICA                                  ~1 h, una sola vez
     Con la cama a 60 grados:
         SCREWS_TILT_CALCULATE
     Devuelve, por tornillo:  "fondo derecha : adjust CW 00:30"
     Girar y repetir hasta que los cuatro den 00:00 a 00:05.

     CRITERIO: los cuatro por debajo de 00:05.
     POR QUE PRIMERO: la malla corrige el residuo de una cama nivelada, no
     reemplaza a nivelarla. Y no puede: fade_end 10 la desvanece, asi que de
     Z=10 para arriba la pieza sale sobre la cama real, torcida y todo.

 A2. UNA MALLA POR TEMPERATURA, EN CALIENTE               ~45 min, una vez
         M140 S60  -> esperar 10 min -> BED_MESH_CALIBRATE PROFILE=pla
         M140 S70  -> esperar 10 min -> BED_MESH_CALIBRATE PROFILE=petg
         M140 S100 -> esperar 15 min -> BED_MESH_CALIBRATE PROFILE=abs
         SAVE_CONFIG
     Son 81 puntos x 3 samples cada una: tarda. Se paga una sola vez, porque
     START_PRINT carga la malla guardada y no re-palpa en cada impresion.
     START_PRINT elige el perfil segun el BED_TEMP que anuncia el laminador, y
     si el que corresponde no existe todavia cae en 'default' y lo dice por
     consola, en vez de abortar la impresion.
     Una sola malla a 60 es la del PLA: el PETG (70) y sobre todo el ABS (100)
     imprimian sobre una cama que no es la que palpo el probe.

     CRITERIO: el rango de la malla que reporta Klipper. Arriba de ~0.3 mm
     conviene volver a A1.
     OJO: en frio no sirve. Aluminio con PEI encima cambia de forma decenas de
     micras entre 20 y 60 grados, y otro tanto entre 60 y 100. Una malla
     palpada en frio corrige una cama que no existe al imprimir, y es una de
     las causas tipicas de que el z_offset sirva para PLA y no para ABS.

 A3. Z OFFSET                                             ~15 min
         PROBE_CALIBRATE  ->  TESTZ Z=-0.05 ...  ->  ACCEPT  ->  SAVE_CONFIG
     O, si ya imprime bien y solo hay que afinar: babystepear durante una
     primera capa hasta que quede, y despues promoverlo con
         Z_OFFSET_APPLY_PROBE + SAVE_CONFIG
     Un babystep suelto NO sobrevive: START_PRINT hace SET_GCODE_OFFSET Z=0.

 A4. TORRE DE RINGING                                     ~20 min
     OrcaSlicer -> Calibration -> Input Shaper (la torre, no el ADXL)
     Medir con calibre la separacion entre ondas, en mm, por eje:
         f = velocidad_del_test / separacion

     QUE HACER CON EL NUMERO: la amplitud residual va como a/(2*pi*f)^2.
         f (Hz)     a=700   a=1000   a=2000   a=4000      (micras)
           25        28       41       81      162
           40        11       16       32       63
           60         5        7       14       28
     El umbral de lo que se ve a contraluz anda por las 20-30 micras. Si X da
     40-60 Hz, outer_wall_acceleration puede subir de 700 sin que se note. Si
     Y da 25 Hz, 700 ya esta al filo y hay que BAJAR. Las dos cosas pueden ser
     ciertas a la vez: hoy hay un solo numero para los dos ejes.

     Es la medicion de mayor valor por minuto invertido de toda la lista, y es
     previa a decidir si el ADXL vale la pena.
```

```
 A5. ROTATION_DISTANCE DEL EXTRUSOR                       ~15 min
     Marcar el filamento a 120 mm de la entrada del extrusor, y despues:
         CALIBRAR_EXTRUSOR
     Extruye 100 mm a 1 mm/s (lento a proposito: a caudal alto el engranaje
     patina y medis el patinaje, no la geometria). Al terminar, medir lo que
     queda hasta la marca:
         consumido = 120 - R
         nuevo rotation_distance = 26.359 * (120 - R) / 100
     Editar [extruder] en hardware.cfg y repetir.

     CRITERIO: consumir 100 +/- 0.5 mm.
     POR QUE ANTES DE LA FASE B: rotation_distance traduce vueltas de motor en
     milimetros de filamento, y B1 y B2 miden encima. Si esta mal, esas dos
     torres miden bien un numero equivocado. Y hay indicio de que lo esta: los
     filament_flow_ratio del repo son 0.98 / 0.95 / 0.98 / 1.00, y tres de
     cuatro por debajo de 1 sugiere un sesgo comun, o sea un error del
     engranaje -constante de la MAQUINA- corregido cuatro veces por separado
     en una clave de MATERIAL.
```

### Fase B - el material (no toca el firmware)

```
 B1. MAX FLOWRATE                                         ~30 min por material
     OrcaSlicer -> Calibration -> Max Flowrate
     -> filament_max_volumetric_speed en profiles.py

     POR QUE ANTES QUE TODO LO DEMAS DEL MATERIAL: el auto-freno de la seccion
     7 solo protege si el numero que lo dispara es honesto. Con un techo
     optimista Orca no frena y el relleno sub-extruye sin dar sintoma. El 10
     del PLA es una estimacion conservadora, no una medicion, y es el unico
     valor de esta lista que puede estar afectando la calidad AHORA MISMO.

 B2. FLOW RATE                                            ~30 min por material
     OrcaSlicer -> Calibration -> Flow Rate (pass 1, despues pass 2)
     -> filament_flow_ratio
     Sin esto todo lo que se mida despues mide mal.

 B3. TEMPERATURA                                          ~30 min por material
     OrcaSlicer -> Calibration -> Temperature Tower
     -> nozzle_temperature / nozzle_temperature_initial_layer
     Contrastar con la etiqueta del rollo de Printalot.

 B4. PRESSURE ADVANCE                     <- el de mas impacto visual
     OrcaSlicer -> Calibration -> Pressure Advance (modo Tower)
     Lo pone KLIPPER, no el laminador: la tabla variable_pa del macro
     START_PRINT en versions/<CURRENT>/macros.cfg.
         PLA 0.04   PETG 0.06   ABS 0.05   TPU 0.6
     Cambiar el valor EN LOS DOS LADOS (variable_pa y la clave
     pressure_advance del filamento). `orca.py check` falla si quedan
     distintos.
     Para experimentar sin tocar el firmware: poner enable_pressure_advance en
     ["1"] en ese filamento, y Orca lo pisa.

 B5. RETRACCION                                           ~20 min por material
     OrcaSlicer -> Calibration -> Retraction test

 B6. TOLERANCIA / AGUJEROS                                ~30 min
     OrcaSlicer -> Calibration -> Tolerance
     -> xy_hole_compensation y elefant_foot_compensation, hoy en valores
        genericos NO medidos (0 y 0.15).
         xy_hole_compensation = (nominal - medido) / 2
     Un agujero sale sistematicamente mas chico que el modelo: el perimetro
     interno es convexo hacia adentro y el plastico se contrae hacia el centro
     del arco. En un nozzle 0.4 el error tipico es 0.05-0.15 mm de diametro, o
     sea si entra un M5 o no.
     Esta sin compensar A PROPOSITO: una compensacion mal puesta se aplica a
     todos los agujeros de todas las piezas e introduce un error sistematico en
     la direccion contraria. Peor que no compensar.
```

### Fase C - input shaper (requiere hardware y tocar `printer.cfg`)

Es el único cambio de toda la lista que mejora **calidad y velocidad a la vez**.
Todo lo demás es una permuta. Pero llegar acá sin haber hecho A1 y A2 es
acelerar sobre una cama que no conocés.

```
 C1. Comprar una placa ADXL345 USB (tipo "Portable Input Shaper").
     Las secciones [mcu adxl] / [adxl345] / [resonance_tester] ya estan
     escritas y comentadas en hardware.cfg, con el pinout tipico.

 C2. El procedimiento completo esta en limits.cfg. Dos cosas que se pierden:
       - Klipper NO arranca si esas secciones estan activas y la placa
         desenchufada. Se descomenta para calibrar y se vuelve a comentar.
       - En un bed slinger, Y se mide con el acelerometro EN LA CAMA, no en el
         carro. En Y no se mueve el hotend: se mueve la cama con la pieza
         encima. Es otra masa, otra resonancia, y encima cambia con el peso de
         lo que se este imprimiendo. Medir Y desde el carro mide el eje
         equivocado.

 C3. Recien despues, subir las aceleraciones de IMPRESION (tabla abajo).
```

### Valores a subir después del input shaper

Ojo con qué se mueve. `[printer] max_accel` es el techo **mecánico** y ya está
en 3000 para que respire el travel; lo que el shaper destraba es el
**presupuesto de ringing**, que son las aceleraciones de impresión.

```
                                  ahora          post input shaper
 -----------------------------------------------------------------
 [printer] max_accel (Klipper)     3000              5000
 minimum_cruise_ratio                 0                 0   (ya esta)
 default_acceleration              2000              4000
 inner_wall_acceleration           2000              4000
 outer_wall_acceleration            700              2500
 top_surface_acceleration           700              2500
 travel_acceleration               3000              5000
 initial_layer_acceleration         500               500   (no tocar)

 outer_wall_speed (Standard)         50                90
 inner_wall_speed (Standard)        110               150   (*)
 travel_speed                       250               280
```

(*) Ojo con `inner_wall_speed`: a 150 mm/s con capa 0.20 y ancho 0.45 el caudal
es 13.5 mm3/s, muy por encima del techo del hotend. Si subís ahí, B1 (Max
Flowrate) deja de ser opcional. Es probable que el hotend stock sea el cuello de
botella real y no la mecánica.

Recordá que `machine_max_acceleration_x / y` de `MACHINE` tienen que seguir a
`max_accel` o `check` falla: son su espejo para la estimación de tiempo.

Editá `orcakit/profiles.py` y corré `python orca.py build`, así los cambios
quedan versionados en un solo lugar y no dispersos en la UI. El diff de git en
`presets/` te va a mostrar exactamente qué cambió.

---

## 9. Verificación hecha

La configuración no está solo escrita, está comprobada.

| Chequeo | Resultado |
|---|---|
| Los 9 presets cargan en OrcaSlicer | 9 de 9 `load config successful` |
| Claves o valores rechazados por Orca | `returned substitutions 0` |
| Selección activa al abrir | EnderS1ProKlipper / 0.20mm Standard / Printalot PLA |
| Errores en el log de arranque | ninguno |
| Valores agresivos heredados del preset de fábrica | 0 sobrevivieron |
| Checksum MD5 de `OrcaSlicer.conf` | recalculado y verificado |

`returned substitutions 0` es el chequeo importante: significa que OrcaSlicer
aceptó **todas** las claves y **todos** los valores tal cual fueron escritos, sin
corregir ni descartar ninguno.

Durante la validación apareció un defecto real que quedó corregido: faltaba
`G92 E0` en el g-code de cambio de capa, obligatorio con extrusión relativa.

### Primera impresión real

`SoporteCocina-Body`, 43 min, 4.52 m de PLA, con `0.20mm Standard` y
`Printalot PLA`. Completada sin problemas y rápida. Los defectos que quedaron
fueron sutiles y dispararon la revisión que documenta la sección siguiente:

- un agujero chico impreso sin soportes salía ligeramente deformado
- los bordes redondeados no salían del todo suaves

---

## 10. Revisión de calidad

Tres causas concretas, con su corrección:

| Causa | Evidencia | Corrección |
|---|---|---|
| Klipper partía los arcos en cuerdas de 1 mm | `[gcode_arcs] resolution = 1.0` consultado por API. En un radio de 2 mm eso son 0.064 mm de faceta | Primero se apagó `enable_arc_fitting`. Desde `versions/v3` se arregla de raíz: `resolution` en `limits.cfg` (0.1 al principio, hoy 0.2) y el arc fitting vuelve a estar prendido |
| Pressure advance apagado | El g-code impreso tenía `enable_pressure_advance = 0` y Klipper reportaba `pressure_advance = 0.0` | Lo pone `START_PRINT` según el `MATERIAL` que anuncia el laminador, así lo hereda cualquier g-code |
| Techo de un agujero sin soporte | El perímetro en voladizo arrancaba en el aire | `overhang_reverse` y `extra_perimeters_on_overhangs` en 1 |

Además, como sin input shaper la amplitud del ringing la manda la aceleración y
no la velocidad, la pared exterior y la superficie superior bajaron de 1000 a
**700 mm/s²**, y la pared exterior de 60 a **50 mm/s**. El resto del perfil se
quedó en el techo de 2000: el relleno y las paredes internas no se ven.

El costo en tiempo es del orden del 10 al 15 %. Draft quedó sin tocar: si la
pieza tiene que verse bien, va Standard.

**Lo que sigue sin verificarse**: el CLI de OrcaSlicer en Windows no resuelve la
herencia de presets de usuario, así que no hay forma de laminar automáticamente
para comparar. La validación es imprimir.

### Primera prueba sugerida

```
 1. Un cubo de calibración de 20 mm en PLA con 0.20mm Standard.
    Mirá: primera capa pareja, esquinas sin abultado, medidas 20.0 +/- 0.15.

 2. Si las esquinas salen abultadas o las paredes con "eco",
    es falta de pressure advance. Andá al paso B4 de la sección 8.

 3. Confirmá que Mainsail te muestre la miniatura de la pieza en la cola.
```

---

## 11. Backup y restauración

Todo vive en el repositorio git `~/nd.printer`, que tiene las dos mitades:

```
 nd.printer/
 |
 +-- versions/                  LA MAQUINA
 |   +-- CURRENT                que version esta viva
 |   +-- v3/hardware.cfg        pines, sensores, PID, offsets
 |   +-- v3/limits.cfg          [printer] [gcode_arcs] [idle_timeout]
 |   +-- v3/macros.cfg          START_PRINT / END_PRINT
 |   +-- v3/printer.cfg.example plantilla del archivo mutable
 |
 +-- orca/                      EL LAMINADOR
 |   +-- orca.py                    CLI: where build install verify audit check
 |   +-- orcakit/profiles.py       FUENTE DE VERDAD: los 10 perfiles
 |   +-- orcakit/presets.py        la forma de un preset (dataclasses, sin valores)
 |   +-- orcakit/snapshot.py       construccion y comparacion de presets/
 |   +-- orcakit/values.py         los valores de texto de Orca y Klipper, a numeros
 |   +-- orcakit/orcapaths.py      localizacion cross-platform del data dir
 |   +-- orcakit/printhost.py      resolucion del host de impresion
 |   +-- orcakit/confpatch.py      parcheo de OrcaSlicer.conf con recalculo del MD5
 |   +-- orcakit/flatten.py        resuelve la cadena de herencia
 |   +-- orcakit/klippercfg.py     parser de los .cfg de Klipper
 |   +-- orcakit/report.py         hallazgos de una validacion y su renderizado
 |   +-- orcakit/audit.py          auditoria de caudales y temperaturas
 |   +-- orcakit/checkcfg.py       validacion cruzada entre las dos mitades
 |   +-- tests/                    unittest de la stdlib, sin dependencias
 |   +-- presets/               snapshot versionado que consume OrcaSlicer
 |   +-- docs/                  este documento y su version web
 |
 +-- backup/20260826-original/  la configuracion previa a este repo
```

La mitad de Klipper la despliega a la Raspberry el rol `klipper_config` de
nd.homelab; la de OrcaSlicer se instala en cada PC con `orca.py install`.

`orca.py install` deja además un backup con timestamp en `backup/<fecha>/`
antes de escribir nada.

**Para restaurar lo viejo**: cerrá OrcaSlicer, borrá el `user/default/` del
directorio de datos y copiá encima `backup/20260826-original/user/`, más el
`OrcaSlicer.conf`.

**Para reinstalar la configuración nueva**: cerrá OrcaSlicer y corré
`python orca.py install`.

---

## 12. Resumen de decisiones

| Decisión | Motivo |
|---|---|
| Aceleraciones de impresión a 2000 y no más | Es el presupuesto de ringing sin input shaper. No es lo mismo que `[printer] max_accel`, que es el techo mecánico y está en 3000 |
| `max_accel` 3000 pero travel el único que lo usa | Atar el techo mecánico al presupuesto de ringing hacía que el travel pagara una restricción de calidad superficial que no le corresponde: el ringing de un desplazamiento por el aire no deja marca. A 2000, llegar a los 250 mm/s de travel exigía 15.6 mm y casi ningún travel real es tan largo |
| Pared exterior a 700 mm/s2 | Sin input shaper, la amplitud del ringing la manda la aceleración, no la velocidad. Solo se baja donde se ve |
| Un proceso por geometría y no 5x4 por material | El techo de caudal del filamento hace el ajuste por material automáticamente |
| ABS es la única excepción, con proceso propio | `brim_type` y `draft_shield` son claves de PROCESO y un filamento no las puede pisar. Sin el quinto proceso, la fuente de verdad documentaba un paso manual en la UI que `check` no podía verificar |
| El proceso ABS NO baja la velocidad | Sin caja, el modo de falla es la delaminación: ir más lento le da más tiempo a la capa de abajo para enfriarse. La contramedida es más calor por capa, no menos velocidad |
| Planchado solo en Fine y Standard | Es la mitad que faltaba de la cara superior, y cuesta tiempo solo ahí. En Strong y Draft es tiempo en una superficie que a nadie le importa |
| Perfiles que heredan en vez de autocontenidos | Sobreviven a las actualizaciones de OrcaSlicer |
| `compatible_printers` en todo | Listas limpias: solo ves lo que aplica a esta impresora |
| Pressure advance pre-cargado pero apagado | Elegiste no tocar firmware; queda a un click de distancia y sin sorpresas |
| `emit_machine_limits_to_gcode` en 0 | Los límites los define `printer.cfg`, no el laminador |
| Temperaturas iguales en todos los tipos de placa | Imposible equivocarse con el "Bed type" seleccionado |
| Skirt en 0 | `START_PRINT` ya purga con dos líneas completas |
| Área imprimible 220x220 y no 250x235 | `position_max` es el recorrido del carro, no el tamaño de la chapa. El carro llega más lejos que el plato |
| Techo de caudal del PLA en 10 y no 11 | El auto-freno de la sección 7 solo protege si el número que lo dispara es honesto. 11 nunca se midió, y el proceso pedía el 98 % de él |
| ABS a 255 y no 245 | Sin encerramiento el modo de falla es la delaminación, no el warp. Más calor por capa es la contramedida estándar, y el hotend llega a 300 |
| Eje Z a 10 / 200 y no 5 / 100 | 5/100 eran los valores del archivo de ejemplo de Klipper, no de esta máquina. Con husillo TR8x8, 5 mm/s son 37 rpm |
| Scarf joint solo en Fine, Standard y Strong | Reparte la costura en rampa. En Draft es tiempo gastado en una superficie que nadie mira |
| `wall_sequence` en los procesos de 3 paredes o más | inner-outer-inner necesita 3 para significar algo. Con `wall_loops: 2` degenera al orden normal, así que Fine y Draft se quedan afuera |
| Malla con `fade_end: 10` | Sin fade la corrección se suma al Z en todas las capas y una pieza alta reproduce la panza de la cama entera |
| `samples: 2` en el BLTouch y malla 9x9 | El default era UNA lectura por punto y un paso de 39x44 mm. Como `START_PRINT` carga una malla guardada en vez de re-palpar, ser más denso y más lento cuesta cero tiempo de impresión |
| `screws_tilt_adjust` además de `bed_screws` | Había un probe y se nivelaba con un papel. La malla corrige el residuo de una cama nivelada; no la reemplaza, porque `fade_end: 10` la desvanece |
| `retraction_minimum_travel` 2 mm y no 1 | A 1 mm el Sprite retraía en prácticamente cada travel: cientos de transitorios de presión por capa |
| Compensaciones dimensionales sin tocar | Una compensación mal puesta introduce un error sistemático en la dirección contraria. Peor que no compensar. Salen del paso 7 de la sección 8 |
