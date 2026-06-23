# v2 — Actualización firmware MCU Klipper (Ender 3 S1 Pro)

Fecha: 2026-06-23

## Motivo
El host de Klipper se actualizó a `v0.13.0-699-gc707dd192` y el MCU quedó en
`v0.12.0-178-g7e8c7f46`. El desfasaje rompió la comunicación
("Lost communication with MCU" → printer en shutdown). Se recompila el firmware
del MCU para que coincida con el host.

## Placa
- MCU: STM32F401 (`stm32f401xc`), board Creality CR-FDM-v24S1 (Ender 3 S1 Pro)
- Conexión host↔MCU: chip CH340 (`1a86 USB Serial`) → USART1, 250000 baud
- Serial path: `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0`

## Build (make menuconfig) — ver `klipper-build.config`
- Micro-controller Architecture: STMicroelectronics STM32
- Processor model: STM32F401
- Bootloader offset: **64KiB bootloader**  (CONFIG_STM32_FLASH_START_10000)
- Clock Reference: **8 MHz crystal**       (CONFIG_CLOCK_REF_FREQ=8000000)
- Communication interface: **Serial (on USART1 PA10/PA9)**
- Baud rate: 250000 (default)

## Verificación contra v1 (known-good)
Vector de arranque de ambos binarios → misma base de flash 0x08010000 (64 KiB),
mismo stack pointer 0x20010000. Confirma que el offset coincide con v1.

| binario            | reset vector | base flash      |
|--------------------|--------------|-----------------|
| v1 klipper_v1.bin  | 0x0801020d   | 0x08010000 (64K)|
| v2 klipper_v2.bin  | 0x080169fd   | 0x08010000 (64K)|

Tamaño 27 KB (v0.12) → 42 KB (v0.13): normal por el cambio de versión; entra de
sobra en los 192 KB útiles del F401.

## Flasheo (tarjeta SD)
1. Copiar `firmware/STM32F4_UPDATE/klipper_v2.bin` a la carpeta `STM32F4_UPDATE`
   de la microSD (FAT32) que va en el slot frontal de la impresora.
2. Apagar la impresora, insertar la SD, encender. La pantalla NO debe mostrar el
   menú normal (~10-30s) = flasheó.
3. Apagar, **sacar la SD** (sino re-flashea en cada arranque), encender.
4. En Mainsail: `FIRMWARE_RESTART`. Verificar que mcu_version == host.
