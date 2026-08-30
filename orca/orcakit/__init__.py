"""Toolkit de configuración de OrcaSlicer para la Ender 3 S1 Pro con Klipper.

Los módulos, de más fundamental a más derivado:

    values      conversión de los valores de texto de Orca y Klipper a números
    presets     las dataclasses que definen la forma de un preset de OrcaSlicer
    profiles    LOS DATOS: los nueve perfiles y el porqué de cada valor
    snapshot    construcción y comparación del snapshot de presets/
    orcapaths   localización del directorio de datos de OrcaSlicer
    printhost   resolución del host de impresión, que no se versiona
    confpatch   parcheo de OrcaSlicer.conf con recálculo del MD5
    flatten     resolución de la cadena de herencia de un preset instalado
    klippercfg  parser de los .cfg de Klipper
    report      acumulación y renderizado de los hallazgos de una validación
    audit       auditoría de los valores finales de lo instalado
    checkcfg    validación cruzada entre los presets y la config de Klipper

El CLI que los orquesta es orca/orca.py.
"""
