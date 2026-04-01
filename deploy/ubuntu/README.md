# Despliegue Ubuntu

Este directorio usa un unico punto de entrada:

- `cobien-launcher.sh`

Ese script se encarga de:

- preparar el entorno
- instalar dependencias del sistema
- instalar `uv`
- asegurar `Python 3.11`
- crear o recrear `.venv`
- generar `cobien-update.env`
- lanzar el sistema del mueble
- actualizar repos y relanzar
- vigilar cambios cada minuto
- instalar una tarea cron

## Uso normal

```bash
bash cobien-launcher.sh
```

Si se ejecuta sin parametros:

- pregunta si quieres usar modo desatendido
- si respondes que no, entra en modo guiado
- si respondes que si, usa los valores por defecto

## Modos

Flujo completo:

```bash
bash cobien-launcher.sh
```

Flujo completo desatendido:

```bash
bash cobien-launcher.sh --non-interactive --yes --workspace /home/cobien/cobien
```

Solo preparar entorno:

```bash
bash cobien-launcher.sh --mode setup --workspace /home/cobien/cobien
```

Solo lanzar el sistema:

```bash
bash cobien-launcher.sh --mode launch --workspace /home/cobien/cobien
```

Actualizar una vez:

```bash
bash cobien-launcher.sh --mode update-once --workspace /home/cobien/cobien
```

Vigilar cambios:

```bash
bash cobien-launcher.sh --mode watch --workspace /home/cobien/cobien
```

Ver configuracion resuelta:

```bash
bash cobien-launcher.sh --mode dry-run --workspace /home/cobien/cobien
```

## Version de Python

El frontend debe desplegarse con `Python 3.11`.

El launcher:

- usa `python3.11` si esta disponible
- intenta instalarlo si Ubuntu lo ofrece
- usa `uv` para gestionar Python y el entorno

## Entorno con uv

El despliegue usa:

- instalador oficial de Astral para `uv`
- `uv python install`
- `uv venv`
- `uv sync`

Dependencias del frontend:

- [pyproject.toml](/home/aritz/Development/DT/Projects/cobien/cobien_FrontEnd/CoBienICAM-main/frontend-mueble/pyproject.toml)

## Cron

Si quieres actualizar solo a ciertas horas:

```cron
0 3,15 * * * /bin/bash /home/cobien/cobien/cobien_FrontEnd/deploy/ubuntu/cobien-launcher.sh --mode update-once --workspace /home/cobien/cobien >> /home/cobien/cobien-update.log 2>&1
```

## Notas

- `cobien-launcher.sh` es el unico punto de entrada operativo.
- El sistema solo actualiza si la rama actual coincide con `development_fix`.

## systemd (recomendado)

En lugar de `.desktop` o `bashrc`, se recomienda usar `systemd --user`.

Archivos incluidos:

- `deploy/ubuntu/systemd/cobien-launcher.service`
- `deploy/ubuntu/systemd/cobien-update.service`
- `deploy/ubuntu/systemd/cobien-update.timer`
- `deploy/ubuntu/install-systemd-user.sh`

Instalacion:

```bash
bash deploy/ubuntu/install-systemd-user.sh
```

Esto habilita:

- arranque automatico del launcher al iniciar sesion de usuario
- comprobacion diaria de actualizaciones a la 01:00

Comandos utiles:

```bash
systemctl --user status cobien-launcher.service
systemctl --user list-timers | grep cobien-update
journalctl --user -u cobien-launcher.service -f
```

Aplicar cambios tras una actualizacion del repo:

```bash
cd ~/cobien/cobien_FrontEnd
bash deploy/ubuntu/install-systemd-user.sh
systemctl --user daemon-reload
systemctl --user restart cobien-launcher.service
```
