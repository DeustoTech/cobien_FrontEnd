# CoBien Smart Furniture App

Software del mueble inteligente del proyecto europeo CoBien, orientado a la inclusión digital de personas mayores. La app corre en un PC embebido y ofrece: asistente de voz, calendario con MongoDB, tiempo, recordatorios, chistes/curiosidades, videollamada y mensajería MQTT.

## Tecnologias

- Python 3.10+
- Kivy (UI)
- Vosk (ASR offline) + pyttsx3 (TTS offline)
- Transformers (RoBERTa) + scikit-learn (NLP intenciones)
- MongoDB Atlas + PyMongo (eventos)
- OpenWeather + Open-Meteo (tiempo)
- paho-mqtt (mensajería)
- PyQt5 / QWebEngine (videollamada web embebida)

## Estructura general

app/
│
├── mainApp.py                 # Ventana principal (Kivy) y orquestación UI
├── mqtt_publisher.py          # Tester MQTT (CLI)
│
├── events/
├── weather/
├── reminders/
├── jokes/
├── videocall/
├── virtual_assistant/
├── board/                      # Pendiente de desarrollo
│
├── data/images/
└── logs/

## Módulos y archivos (detallado)

### 1) events/ — calendario y agenda

Objetivo: cargar eventos desde MongoDB (con filtro por ciudad y dispositivo), mantener caché local y mostrar un calendario mensual con detalle diario. Dispara refresh entre pantallas mediante un event bus.

#### loadEvents.py
- Conexión a MongoDB Atlas.
- Filtros aplicados:
  - audience="all" AND location="Bilbao" (públicos)
  - audience="device" AND target_device="maria" AND location="Bilbao" (personales del dispositivo)
- Normalización:
  - Formato fecha dd-mm-YYYY.
  - Colores por audiencia.
  - Añade id (string de _id) para operaciones de borrado.
- Caché local:
  - Guardar eventos en events/eventos_local.json.
  - Cargar caché con filtro location si no hay red.
- CRUD:
  - delete_event_mongo(event_id).
  - add_personal_event_mongo(day_date,title,description,location,device).
- Notificación global: tras add/delete → event_bus.notify_events_changed().

#### eventsScreen.py
- Pantalla mensual tipo tarjeta con:
  - Cabecera con fecha/hora en vivo y leyenda (público azul / personal rojo).
  - Calendario 6×7: celdas DayCell con puntos.
  - Casilla “HOY” resaltada.
  - Flechas para cambiar de mes.
- Carga de datos:
  - EventStore.reload() → fetch_events_from_mongo() (o caché).
- Navegación:
  - Pulsar día abre DayEventsScreen.
- Actualización:
  - on_pre_enter() y refresh_calendar() recargan store y reconstruyen la rejilla.
  - Se suscribe al event_bus.

#### dayEventsScreen.py
- Lista de eventos del día (scroll), ordenando públicos primero.
- Cada fila EventRow:
  - Punto de color por audiencia.
  - Papelera habilitada solo en personales.
- Voz para añadir (Vosk):
  - voice_add() → pide título y descripción por voz.
  - Inserta con add_personal_event_mongo() y notifica al bus.
- Sincronización cruzada:
  - Tras add/delete, refresca eventos en la pantalla principal.
- Navegación por días con flechas.
- Cabecera: fecha/hora y botones back/voice.

#### event_bus.py
- EventBus(EventDispatcher) con evento on_events_changed.
- notify_events_changed() para disparar updates.

### 2) weather/ — tiempo actual, franja horaria y 6 días

#### weatherScreen.py
- Diseño:
  - Dos tarjetas simétricas: cabecera (condición actual + franja horaria) y seis días.
  - Botones Volver y Voz iguales a la pantalla principal.
  - Tarjetas de día sin borde.
- Datos:
  - OpenWeather para condición actual e idioma ES.
  - Open-Meteo:
    - hourly para 12 horas próximas.
    - daily para 6 días (tmin, tmax, prob. precip).
- Actualización:
  - Hilo de refresco cada 20 min (Clock + threading.Thread).
  - Mapea iconos (sol/noche/nubes/lluvia/niebla/nieve/tormenta) a imágenes locales.
- TTS:
  - speak_window_info() narra condición, temperatura y min/max del día con pyttsx3.
- Utilidades:
  - _render_hourly() y _render_daily() para construir widgets.
  - _map_icon_owm() y _map_icon_openmeteo() para iconos.
- Auxiliar: weather_today.json (persistencia simple de min/max observados).

### 3) virtual_assistant/ — voz → intención → acción → voz

#### Flujo
1. recognizer.py (Vosk) escucha y transcribe.
2. nlp_processor.py obtiene embedding RoBERTa y lo pasa al clasificador.
3. actions.py ejecuta la intención.
4. main_assistant.py orquesta el flujo y TTS.

#### actions.py
- Router de intenciones → métodos:
  - ver_eventos, iniciar_llamada
  - consultar_fecha, consultar_hora, consultar_clima, consultar_pronostico
  - configurar_recordatorio, establecer_recordatorio
  - consultar_noticias, consultar_receta, contar_chiste, saludar, despedirse
- Extractores: tiempo del recordatorio y receta.
- Integración UI: cambiar pantalla y TTS.

#### intent_classifier.py
- Carga intent_dataset.json.
- Genera embeddings RoBERTa.
- Entrena LogisticRegression.
- Guarda artefactos para inferencia offline.

#### nlp_processor.py
- Carga clasificador, encoder y modelo/tokenizer RoBERTa locales.
- Predice intención.

#### recognizer.py
- Instancia Vosk y stream de audio sounddevice (16 kHz mono).
- Devuelve texto.

#### main_assistant.py
- Orquesta interacción con feedback visual y TTS fallback.

#### Datos
- intent_dataset.json (frases de ejemplo).

### 4) jokes/

#### jokesScreen.py
- Carga dataset mrm8488/CHISTES_spanish_jokes.
- Carga diferida (Clock).
- Muestra un chiste aleatorio.
- Evita repetir el último.

### 5) reminders/

#### reminders.py
- RecordatorioManager con persistencia en reminders/recordatorios.json.
- Crea y programa recordatorios con Clock.schedule_once.
- Reprograma pendientes al iniciar.
- Muestra recordatorios con app.speak_text y los elimina tras ejecutarse.

### 6) videocall/
- Ventana PyQt5/QWebEngine que carga la web del proyecto.
- Sala y usuario por defecto: Maria.
- Pantalla completa; botón salir vuelve a la app.

### 7) mqtt_publisher.py
- CLI de pruebas MQTT.
- Broker: broker.hivemq.com (port 1883).
- Topics: tarjeta y videollamada.
- Publica manualmente para pruebas.

## Ficheros de datos / logs

| Ruta | Contenido |
|---|---|
| events/eventos_local.json | Caché local de eventos |
| reminders/recordatorios.json | Recordatorios pendientes |
| weather/weather_today.json | Min/Max observados del día |

## Instalación

1) Requisitos
- Python 3.10+
- VLC instalado
- PortAudio (para sounddevice/Vosk)
- Tkinter (para los popups)
- Cámara web funcional

2) Dependencias (UV)
- Usar la fuente de dependencias del proyecto:
  - `uv sync --project .`
- Con versión explícita de Python (opcional):
  - `uv sync --project . --python 3.13`

3) Claves y conexión
Opciones recomendadas:
- `app/config/config.local.json` para una configuración completa por mueble
- variables de entorno para despliegues gestionados por `systemd` o launcher

Orden de prioridad:
1. Variables de entorno
2. `app/config/config.local.json`

En `config.local.json` puedes guardar conjuntamente:
- secretos (`MONGO_URI`, `OWM_API_KEY`, `NEWS_API_KEY`, `SPOONACULAR_API_KEY`, `COBIEN_NOTIFY_API_KEY`)
- URLs y brokers
- opciones del mueble (`device_id`, `videocall_room`, `device_location`, etc.)

4) Ejecución
- `uv run --project . mainApp.py`   # solo interfaz (sin cámara)
- `uv run --project . mqtt_publisher.py`  # prueba MQTT
