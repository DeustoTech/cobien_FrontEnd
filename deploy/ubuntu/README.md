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
- `start_cobien.sh` se mantiene solo como wrapper de compatibilidad.
- El sistema solo actualiza si la rama actual coincide con `development_fix`.
