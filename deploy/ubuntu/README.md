# Despliegue Ubuntu y auto-actualizacion

Este directorio deja preparado el mueble Ubuntu para:

- relanzar el software con rutas configurables
- actualizar `cobien_FrontEnd` y `cobien_MQTT_Dictionnary`
- hacerlo una sola vez o en modo polling cada minuto

## Uso recomendado

Si una persona no tecnica va a usarlo, el punto de entrada recomendado es solo uno:

```bash
bash cobien-first-run.sh
```

Ese asistente pregunta:

- donde estan los proyectos
- si hay que instalar dependencias del sistema
- si hay que borrar el `.venv` anterior
- si quieres hacer una comprobacion de actualizacion antes de lanzar
- si quieres vigilancia cada minuto
- si quieres instalar una tarea cron a ciertas horas

Y despues hace el resto automaticamente.

## Archivos

- `cobien-bootstrap.sh`
- `cobien-update.sh`
- `cobien-update.env.example`

## Bootstrap inicial

Si los dos repos ya estan descargados, puedes preparar todo desde `deploy/ubuntu` con:

```bash
bash cobien-bootstrap.sh --workspace /home/cobien/cobien
```

Eso:

- verifica rutas
- instala dependencias del sistema
- crea `.venv` del frontend
- instala dependencias Python
- deja generado `cobien-update.env`
- deja listos el launcher y el updater

## Version de Python

El frontend actualmente debe desplegarse con `Python 3.11`.

El bootstrap:

- usa `python3.11` si esta disponible
- instala `python3.11` y `python3.11-venv` cuando Ubuntu lo ofrece
- aborta si solo encuentra `Python 3.12+`, porque varias dependencias fijadas del proyecto no son compatibles

## Entorno con uv

El bootstrap ya no usa `pip install -r requirements.txt` como camino principal.

Ahora:

- instala `uv` si no existe
- crea `.venv` con `uv venv`
- sincroniza dependencias desde [pyproject.toml](/home/aritz/Development/DT/Projects/cobien/cobien_FrontEnd/CoBienICAM-main/frontend-mueble/pyproject.toml) usando `uv sync`

Esto hace el despliegue mas reproducible y reduce problemas de resolucion del entorno.

## Primera ejecucion automatizada

Si quieres hacer todo en una sola orden, usa:

```bash
bash cobien-first-run.sh --workspace /home/cobien/cobien
```

Eso ejecuta:

- `cobien-bootstrap.sh`
- carga `cobien-update.env`
- `cobien-update.sh --dry-run`
- `start_cobien.sh`

Si ademas quieres forzar una pasada de actualizacion antes del lanzamiento:

```bash
bash cobien-first-run.sh --workspace /home/cobien/cobien --run-update-once
```

Pero para uso normal no hace falta pasar parametros: el script ya pregunta de forma interactiva.

## Objetivo

La idea es que una persona no tecnica pueda entrar en `deploy/ubuntu` y ejecutar solo:

```bash
bash cobien-first-run.sh
```

Desde ese mismo script se puede:

- preparar el entorno
- reinstalar el `.venv`
- lanzar el mueble
- hacer una actualizacion puntual
- activar vigilancia cada minuto
- instalar cron para actualizacion a ciertas horas

## Modo puntual

Pensado para cron o ejecucion manual:

```bash
bash deploy/ubuntu/cobien-update.sh --once
```

## Modo watch

Consulta Git cada minuto y, si hay cambios en `development_fix`, hace `git pull --ff-only` y relanza el mueble:

```bash
bash deploy/ubuntu/cobien-update.sh --watch
```

## Cron

Para ejecutarlo solo a ciertas horas, usa cron y llama al modo `--once`.

Ejemplo:

```cron
0 3,15 * * * /bin/bash /home/ubuntu/cobien/cobien_FrontEnd/deploy/ubuntu/cobien-update.sh --once >> /home/ubuntu/cobien-update.log 2>&1
```

Eso lo ejecuta a las `03:00` y `15:00`.

## Variables de entorno

Puedes copiar `cobien-update.env.example` a un fichero real y exportarlo antes de lanzar el script.

Variables principales:

- `COBIEN_FRONTEND_REPO`
- `COBIEN_MQTT_REPO`
- `COBIEN_LAUNCH_SCRIPT`
- `COBIEN_UPDATE_REMOTE`
- `COBIEN_UPDATE_BRANCH`
- `COBIEN_UPDATE_INTERVAL_SEC`
- `COBIEN_VENV_ACTIVATE`

## Notas

- El relanzado usa `start_cobien.sh`.
- `start_cobien.sh` ya no depende de rutas hardcodeadas del escritorio antiguo.
- El script solo actualiza si la rama actual coincide con `COBIEN_UPDATE_BRANCH`.
