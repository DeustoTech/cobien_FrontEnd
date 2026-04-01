
# Módulo de Videollamadas – Proyecto CoBien

Este sistema permite realizar videollamadas entre una persona mayor usando el mueble inteligente y un familiar desde la web del proyecto CoBien.

## Descripción General

Cuando un familiar inicia una videollamada desde la web del proyecto, se envía una notificación MQTT al mueble. Este muestra un mensaje de voz y texto informando al usuario. Si el usuario pulsa el botón de "Iniciar videollamada", se abre una ventana independiente (creada con PyQt5) con la videollamada ya activa.

---

## Flujo de funcionamiento

1. La web inicia una videollamada → envía un mensaje MQTT al topic `videollamada` con el nombre del familiar.
2. La app Kivy del mueble está siempre suscrita al topic MQTT y al recibir el mensaje:
   - Muestra un mensaje en pantalla: `Videollamada entrante de Pedro`
   - Reproduce por voz el aviso: `Tienes una videollamada de Pedro`
   - Espera a que el usuario pulse el botón "Iniciar Videollamada"
3. Cuando el usuario pulsa el botón:
   - Se ejecuta el script `videocall_launcher.py`, que abre la página: https://portal.co-bien.eu/videocall/
   - Se rellenan automáticamente los datos necesarios gracias a `CustomWebEnginePage`.

---

## Estructura de archivos

```
videocall/
├── videocallScreen.py       # Pantalla Kivy con el botón de videollamada
├── videocall_launcher.py    # Ventana PyQt5 que abre la videollamada en un navegador embebido
```

---

## Detalles técnicos

### 1. MQTT
- Se utiliza el broker público de HiveMQ: `broker.hivemq.com`
- La app Kivy se suscribe a dos topics:
  - `tarjeta` → para navegación por tarjeta NFC
  - `videollamada` → para videollamadas
- La web hace el papel del publisher. El script `mqtt_publisher.py` es solo para pruebas.

### 2. Navegador embebido con PyQt5
- Usa `QWebEngineView` para mostrar el portal de videollamadas.
- Permisos de micrófono y cámara concedidos automáticamente (`--use-fake-ui-for-media-stream`).
- Prompt automático con el nombre “Maria” para completar el acceso.

---

## Cómo lanzar la videollamada

Desde la interfaz del mueble:
1. Recibir notificación MQTT desde la web
2. Pulsar botón “Iniciar Videollamada”
3. Se lanza `videocall_launcher.py` en una ventana nueva
4. El navegador embebido abre la URL: https://portal.co-bien.eu/videocall/

---

## Notas adicionales

- Si se cierra la ventana de PyQt5, la app vuelve automáticamente a la pantalla principal.
- Se puede lanzar `videocall_launcher.py` de forma aislada para pruebas.

---