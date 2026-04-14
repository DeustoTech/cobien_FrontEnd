
# Módulo de Videollamadas – Proyecto CoBien

Este módulo cubre dos flujos distintos:

1. Videollamada saliente desde la pantalla de contactos del mueble.
2. Videollamada entrante aceptada desde una notificación del sistema.

## Descripción general

La pantalla de contactos no consulta la web en tiempo real para mostrarse. Los
contactos visibles salen del fichero local `app/contacts/list_contacts.txt` y de
las imágenes ya descargadas en `app/contacts/`.

Cuando el usuario pulsa un contacto válido:
- se muestra un popup de espera activa
- se envía una petición HTTP al backend/pizarra
- después se muestra un popup de éxito o de error

Cuando llega una videollamada entrante:
- el backend publica una notificación MQTT
- el frontend muestra el popup entrante
- si el usuario acepta, se lanza `videocall_launcher.py`
- el launcher abre el portal web y notifica al backend que la llamada ha sido atendida

## Flujo actual

### 1. Solicitud saliente desde contactos

1. La pantalla `contactScreen.py` carga `list_contacts.txt`.
2. Solo se muestran contactos con `username` válido.
3. Al pulsar un contacto:
   - aparece `Solicitando videollamada`
   - se llama a `POST /pizarra/api/notify/`
4. Si el backend responde correctamente:
   - se muestra `Notificación enviada`
5. Si falla:
   - se muestra `Solicitud no enviada`
   - los detalles técnicos quedan ocultos detrás de `Mostrar detalles`

### 2. Llamada entrante

1. El backend publica una notificación MQTT de tipo `videocall`.
2. `notification_manager.py` muestra el popup de llamada entrante.
3. Si el usuario acepta:
   - se crea un JSON temporal con `room`, `device_id` e `identity`
   - se lanza `videocall_launcher.py`
   - el launcher abre `portal_videocall_url`
   - el launcher hace `POST /api/call-answered/`
4. Al terminar la llamada se registra la duración y se elimina el JSON temporal.

## Configuración relevante

La configuración sale de `app/config/config.local.json`, sección `services`.

Claves importantes:
- `notify_api_key`
- `pizarra_notify_url`
- `contacts_api_url`
- `portal_videocall_url`
- `portal_call_answered_url`
- `http_timeout_sec`

Y en `settings`:
- `device_id`
- `videocall_room`

## Endpoints backend usados

- `POST /pizarra/api/notify/`
  Envía una solicitud de videollamada al usuario web.

- `GET /pizarra/api/contacts/?device_id=...`
  Devuelve contactos sincronizables para el mueble.

- `POST /pizarra/api/contacts/sync/`
  Publica por MQTT una orden de refresco de contactos.

- `POST /api/call-answered/`
  Marca en backend que el mueble ha aceptado la llamada.

## Códigos de error en videollamada saliente

Cuando falla una solicitud saliente, el popup muestra primero un mensaje simple.
Si el usuario pulsa `Mostrar detalles`, se ven el código y el detalle técnico.

Códigos actuales:
- `VC-CONFIG`: falta `notify_api_key` en configuración.
- `VC-DEVICE`: falta `device_id` en configuración.
- `VC-USER`: el contacto no tiene destino válido.
- `VC-TIMEOUT`: el backend no respondió a tiempo.
- `VC-NET`: error de conexión con backend.
- `VC-REQ`: error HTTP genérico de la librería cliente.
- `VC-401`, `VC-403`, `VC-404`, `VC-500`, etc.: respuesta HTTP del backend.
- `VC-UNK`: error no clasificado.

## Validación de contactos

`list_contacts.txt` usa formato:

```text
NombreVisible=username_backend
```

Ahora el frontend filtra contactos inválidos:
- no se muestran líneas sin `=`
- no se muestran contactos con `username` vacío
- no se muestran contactos con caracteres fuera de `[A-Za-z0-9_.-]`

Ejemplos válidos:

```text
Jules=jules_pourret
Capucine=capucine
Jojo=joisback
```

Ejemplos inválidos:

```text
Mathurin=
Marie=
Simona=
```

## Notas operativas

- Si la web está caída, los contactos pueden seguir viéndose porque salen de caché local.
- Ver contactos no implica que se puedan actualizar ni que se pueda iniciar una llamada.
- `videocall_launcher.py` puede ejecutarse de forma aislada para pruebas, pero el flujo normal usa el JSON temporal generado por `notification_manager.py`.
