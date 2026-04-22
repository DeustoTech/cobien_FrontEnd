# Despliegue Ubuntu

Punto de entrada unico:

- `deploy/ubuntu/cobien-launcher.sh`

Este launcher se encarga de:

- preparar entorno Python/uv
- instalar dependencias del sistema si faltan
- generar/actualizar `deploy/ubuntu/cobien-update.env`
- lanzar CAN + bridge + app
- vigilar actualizaciones en Git y relanzar limpio
- deduplicar procesos/runtime previos

## Modalidades de lanzamiento

Lanzamiento interactivo completo:

```bash
bash deploy/ubuntu/cobien-launcher.sh
```

Lanzamiento desatendido completo:

```bash
bash deploy/ubuntu/cobien-launcher.sh --non-interactive --yes --workspace "$HOME/cobien"
```

Solo preparar entorno:

```bash
bash deploy/ubuntu/cobien-launcher.sh --mode setup --non-interactive --yes --workspace "$HOME/cobien"
```

Solo lanzar runtime (con watcher de updates):

```bash
bash deploy/ubuntu/cobien-launcher.sh --mode launch --non-interactive --yes --workspace "$HOME/cobien"
```

Update puntual:

```bash
bash deploy/ubuntu/cobien-launcher.sh --mode update-once --non-interactive --yes --workspace "$HOME/cobien"
```

Watch continuo sin relanzar manualmente:

```bash
bash deploy/ubuntu/cobien-launcher.sh --mode watch --non-interactive --yes --workspace "$HOME/cobien"
```

Ver configuración resuelta:

```bash
bash deploy/ubuntu/cobien-launcher.sh --mode dry-run --workspace "$HOME/cobien"
```

## Modelo de configuración

Fuente humana principal:

- `deploy/ubuntu/cobien.env`

Artefactos generados:

- `deploy/ubuntu/cobien-update.env`
- `app/config/config.local.json`

Reglas del sistema:

- el humano edita `cobien.env`
- `cobien-launcher.sh` expande ese archivo a `cobien-update.env`
- el launcher regenera `app/config/config.local.json` completo en cada arranque/instalación
- `config.local.json` es un artefacto local del mueble, no un archivo manual
- la app sólo modifica desde UI el subconjunto de claves pensado para gestión local del mueble

## Configuración editable (launcher)

Parámetros relevantes:

- `COBIEN_WORKSPACE_ROOT`: ruta raíz que contiene los dos repos.
- `COBIEN_FRONTEND_REPO_NAME`: carpeta del frontend.
- `COBIEN_MQTT_REPO_NAME`: carpeta del repo MQTT/CAN.
- `COBIEN_UPDATE_BRANCH`: rama de despliegue (por defecto `development_fix`).
- `COBIEN_UPDATE_REMOTE`: remoto Git (normalmente `origin`).
- `COBIEN_UPDATE_INTERVAL_SEC`: intervalo de watch loop en segundos.
- `COBIEN_DEVICE_ID`: id del mueble (`CoBien1`, `CoBien2`, ...).
- `COBIEN_VIDEOCALL_ROOM`: sala de videollamada (case-sensitive).
- `COBIEN_DEVICE_LOCATION`: ciudad/ubicación del mueble.
- `COBIEN_TTS_ENGINE`: motor TTS (`pyttsx3` o `piper`).
- `COBIEN_TTS_PIPER_BIN`: ruta binario `piper` (opcional).
- `COBIEN_TTS_PIPER_MODEL_ES`: ruta modelo Piper español `.onnx`.
- `COBIEN_TTS_PIPER_MODEL_FR`: ruta modelo Piper francés `.onnx`.
- `COBIEN_LOG_DIR`: ruta de logs (opcional; por defecto `<frontend_repo>/logs`).
- `COBIEN_BOOTSTRAP_PYTHON_VERSION`: versión Python solicitada (por defecto `3.13`, con compatibilidad explícita para `3.11`).
- `COBIEN_CAN_BITRATE`: bitrate CAN (por defecto `500000`).
- `COBIEN_CAN_LOG_ENABLE`: `1`/`0` para activar/desactivar `candump`.

La app también permite editar algunos parámetros locales desde:

- Administración -> Parámetros Launcher

Esos cambios se guardan en `app/config/config.local.json`. El launcher respeta en siguientes arranques los ajustes locales interactivos definidos en `app/config_runtime.py`, por ejemplo:

- `settings.weather_cities`
- `settings.weather_city_catalog`
- `settings.weather_primary_city`
- `settings.button_colors`
- `settings.rfid_actions`
- `settings.microphone_device`
- `settings.audio_output_device`
- `settings.joke_category`
- `settings.idle_timeout_sec`
- `notifications.videollamada`
- `notifications.nuevo_evento`
- `notifications.nueva_foto`

Todo lo demás sigue viniendo siempre del despliegue (`cobien.env`).

## systemd (recomendado)

Usar `systemd --user` en lugar de `bashrc` o `.desktop`.

Archivos:

- `deploy/ubuntu/systemd/cobien-launcher.service`
- `deploy/ubuntu/systemd/cobien-update.service`
- `deploy/ubuntu/systemd/cobien-update.timer`
- `deploy/ubuntu/install-systemd-user.sh`

Instalación automática:

```bash
bash deploy/ubuntu/install-systemd-user.sh
```

Este script hace automáticamente:

- instala/actualiza unidades `systemd --user`
- aplica override gráfico (`DISPLAY=:0`, `XAUTHORITY=%t/gdm/Xauthority`)
- elimina `~/.config/autostart/cobien-launcher.desktop` legacy
- elimina entradas cron legacy `--mode update-once`
- `daemon-reload`
- `enable --now cobien-launcher.service`
- `enable --now cobien-update.timer`
- reinicia `cobien-launcher.service`

Además, en primera ejecución de `cobien-launcher.sh` (si no existe `~/.config/systemd/user/cobien-launcher.service`), el launcher fuerza automáticamente:

- instalación de servicios systemd user
- `systemctl --user daemon-reload`
- `systemctl --user enable --now cobien-launcher.service cobien-update.timer`
- `systemctl --user restart cobien-launcher.service`
- verificación de estado activo/enabled

## Operación diaria

Estado del runtime:

```bash
systemctl --user status cobien-launcher.service
```

Ver timer de update:

```bash
systemctl --user list-timers | grep cobien-update
```

Forzar update manual:

```bash
systemctl --user start cobien-update.service
```

Reinicio limpio del runtime:

```bash
systemctl --user restart cobien-launcher.service
```

Logs del launcher:

```bash
journalctl --user -u cobien-launcher.service -f
```

## Procedimientos completos

Reparar mueble existente:

```bash
cd ~/cobien/cobien_FrontEnd
git pull
bash deploy/ubuntu/install-systemd-user.sh
systemctl --user status cobien-launcher.service
```

Despliegue desde cero en mueble nuevo:

```bash
mkdir -p ~/cobien
cd ~/cobien
git clone <URL_FRONTEND> cobien_FrontEnd
git clone <URL_MQTT> cobien_MQTT_Dictionnary
cd cobien_FrontEnd
bash deploy/ubuntu/cobien-launcher.sh --mode setup --non-interactive --yes --workspace ~/cobien --frontend-name cobien_FrontEnd --mqtt-name cobien_MQTT_Dictionnary --branch development_fix
bash deploy/ubuntu/install-systemd-user.sh
```

Configuración de identidad inicial (por CLI):

```bash
bash deploy/ubuntu/cobien-launcher.sh --mode launch --non-interactive --yes --workspace ~/cobien --frontend-name cobien_FrontEnd --mqtt-name cobien_MQTT_Dictionnary --branch development_fix --device-id CoBien1 --videocall-room CoBien1 --device-location Logroño
```

Configuración de TTS con Piper (opcional):

```bash
bash deploy/ubuntu/cobien-launcher.sh --mode launch --non-interactive --yes --workspace ~/cobien --frontend-name cobien_FrontEnd --mqtt-name cobien_MQTT_Dictionnary --branch development_fix --tts-engine piper --tts-piper-model-es "/ruta/modelo-es.onnx" --tts-piper-model-fr "/ruta/modelo-fr.onnx"
```

## Notas importantes

- `cobien-launcher.sh` es el único punto de entrada operativo.
- `deploy/ubuntu/cobien.env` es el único archivo humano de despliegue.
- `app/config/config.local.json` no debe editarse a mano; es estado local generado.
- Evitar lanzar en paralelo scripts antiguos (`start_cobien.sh`, autostart legacy, cron duplicado).
- El sistema actualiza solo si la rama activa del repo coincide con la configurada.
