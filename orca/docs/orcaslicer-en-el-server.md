# Aplicar estos presets al OrcaSlicer del servidor

En el home server (`ndelucca-server`, Fedora) corre un OrcaSlicer containerizado,
desplegado por el rol `orcaslicer` de
[nd.homelab](https://github.com/ndelucca/nd.homelab). Es la **misma versión** que
la de escritorio, así que estos presets le sirven tal cual.

**Esto no está automatizado a propósito.** El procedimiento de abajo está probado
solo parcialmente y hay tres complicaciones reales que lo hacen más caro que el
resto del repo. Si algún día se automatiza, va como `roles/orcaslicer/tasks/presets.yml`.

## Las tres complicaciones

**1. El árbol de config no es de `ndelucca`.** La imagen de linuxserver corre
OrcaSlicer con un uid interno que Podman rootless mapea a un sub-uid del host.
`roles/orcaslicer/tasks/preflight.yml` lo dice explícitamente:

> NO setear owner acá: la imagen LSIO corre OrcaSlicer con un uid in-container
> que rootless Podman mapea a un sub-uid del host, NO a `orcaslicer_user`.
> Forzar la propiedad a `ndelucca` es justo lo que bloquea a la app para escribir.

Así que después de copiar cualquier archivo hay que rehacer el `podman unshare chown`.

**2. SELinux.** El volumen necesita contexto `container_file_t`, y en ese host el
orden de las reglas en `file_contexts.local` importa: gana la última registrada,
no la más específica. El `CLAUDE.md` de nd.homelab documenta el caso donde una
regla amplia de `filebrowser` tapó a la de Immich y produjo un 502 sin dejar
rastro en `ausearch`.

**3. OrcaSlicer reescribe sus configs al cerrarse.** Si el contenedor está
corriendo cuando se inyectan los archivos, los puede pisar. Hay que pararlo antes.

## Procedimiento manual

```sh
# En el server, como ndelucca.
CFG=/srv/disks/D-Draco/appdata/orcaslicer/config

# 1. Parar el contenedor para que no pise lo que se escriba.
systemctl --user stop orcaslicer

# 2. Traer el repo y generar los presets.
git clone https://github.com/ndelucca/nd.printer.git ~/nd.printer
cd ~/nd.printer

# 3. Instalar contra el directorio de datos del contenedor.
#    La ruta exacta adentro depende de donde la imagen ponga el HOME;
#    confirmar con `orca.py where --data-dir <ruta>` antes de escribir.
python3 orca/orca.py where --data-dir "$CFG/.config/OrcaSlicer"
python3 orca/orca.py install --data-dir "$CFG/.config/OrcaSlicer"

# 4. Devolver la propiedad al sub-uid del contenedor.
XDG_RUNTIME_DIR=/run/user/1000 podman unshare chown -R 1000:1000 "$CFG"

# 5. Reetiquetar para SELinux.
sudo restorecon -R "$CFG"

# 6. Arrancar de nuevo.
systemctl --user start orcaslicer
```

## El host de impresión

`orca.py install` inyecta la URL de Moonraker desde `ORCA_PRINT_HOST` o desde
`.printer-host`. En el server ese archivo no existe, así que sin la variable de
entorno el perfil queda con el placeholder y hay que cargar la URL a mano en la
UI. Exportarla antes del paso 3 si se quiere evitar eso.

## Datos de referencia

| Qué | Valor |
|---|---|
| Ruta del config en el host | `/srv/disks/D-Draco/appdata/orcaslicer/config` |
| Ruta adentro del contenedor | `/config` (es el `$HOME` del contenedor) |
| Puerto | `127.0.0.1:3001`, expuesto por NGINX |
| uid/gid del contenedor | `1000:1000` vía sub-uid de podman rootless |
| Unit | `orcaslicer.container` (Quadlet de usuario) |

Los valores vivos están en `roles/orcaslicer/defaults/main.yml` de nd.homelab;
esta tabla es una copia y puede quedar vieja.
