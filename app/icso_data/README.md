# ICSO Telemetry

Este módulo concentra la telemetría ICSO del mueble.

## Qué genera

- `app/logs/icso_log.json`
  - snapshot agregado del estado ICSO
- `app/logs/icso_log.txt`
  - histórico de eventos generales
- `app/logs/icso_proximity_sensors.txt`
  - histórico de eventos de proximidad

## Sincronización con backend

La sincronización HTTP se realiza desde `sync_service.py`.

### Endpoints esperados

- `services.icso_telemetry_url`
  - `POST` snapshot agregado
- `services.icso_events_url`
  - `POST` lote incremental de eventos nuevos

### Autenticación

Se reutiliza `services.notify_api_key` mediante cabecera:

- `X-API-KEY: <notify_api_key>`

### Comportamiento

- al arrancar la aplicación se intenta sincronizar un snapshot completo
- cada escritura de log programa una sincronización en background
- el estado de sincronización se guarda en:
  - `app/runtime_state/icso_sync_state.json`

## Consulta local

El panel de administración del frontend puede leer los ficheros locales de ICSO.

La consulta web del backend queda disponible en:

- `/pizarra/icso/`
