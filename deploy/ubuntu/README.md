# Despliegue Ubuntu y auto-actualizacion

Este directorio deja preparado el mueble Ubuntu para:

- relanzar el software con rutas configurables
- actualizar `cobien_FrontEnd` y `cobien_MQTT_Dictionnary`
- hacerlo una sola vez o en modo polling cada minuto

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
