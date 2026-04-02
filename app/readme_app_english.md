# CoBien Smart Furniture App

Software for the CoBien smart furniture project, aimed at digital inclusion for elderly users. The app runs on an embedded PC and provides: voice assistant, calendar with MongoDB, weather, reminders, jokes, video calls, and MQTT messaging.

## Stack

- Python 3.10+
- Kivy (UI)
- Vosk (offline ASR) + pyttsx3 (offline TTS)
- Transformers (RoBERTa) + scikit-learn (NLP intent classification)
- MongoDB Atlas + PyMongo (events)
- OpenWeather + Open-Meteo (weather)
- paho-mqtt (messaging)
- PyQt5 / QWebEngine (embedded video call)

## General Structure

app/
│
├── mainApp.py                 # Main window (Kivy) and UI orchestration
├── mqtt_publisher.py          # MQTT CLI tester
│
├── events/
├── weather/
├── reminders/
├── jokes/
├── videocall/
├── virtual_assistant/
├── board/                      # Pending development
│
├── data/images/
└── logs/

## Modules and Files (Detailed)

### 1) events/ — Calendar and Schedule

Purpose: load events from MongoDB (filtered by city and device), maintain local cache, and display a monthly calendar with daily details. Synchronizes across screens through an event bus.

#### loadEvents.py
- Connects to MongoDB Atlas.
- Filters applied:
  - audience="all" AND location="Bilbao" (public)
  - audience="device" AND target_device="maria" AND location="Bilbao" (personal device events)
- Normalization:
  - Date format dd-mm-YYYY.
  - Color by audience.
  - Adds id (string of _id) for deletion.
- Local cache:
  - Save to events/eventos_local.json.
  - Load cached data if offline.
- CRUD:
  - delete_event_mongo(event_id).
  - add_personal_event_mongo(day_date,title,description,location,device).
- Global notification: after add/delete → event_bus.notify_events_changed().

#### eventsScreen.py
- Monthly card-like calendar:
  - Header with live date/time and legend (public blue / personal red).
  - 6×7 grid of DayCells with color dots.
  - Highlighted “TODAY” cell.
  - Month navigation arrows.
- Data loading:
  - EventStore.reload() → fetch_events_from_mongo() (or cache).
- Navigation:
  - Clicking a day opens DayEventsScreen.
- Updates:
  - on_pre_enter() and refresh_calendar() reload and rebuild the grid.
  - Subscribed to event_bus for live refresh.

#### dayEventsScreen.py
- Daily list of events (scroll), sorting public first.
- Each row EventRow:
  - Color dot per audience.
  - Delete button enabled only for personal events.
- Voice add (Vosk):
  - voice_add() → asks for title and description by voice.
  - Inserts using add_personal_event_mongo() and triggers bus notification.
- Cross-screen sync:
  - After add/delete, refresh main calendar.
- Day navigation with arrows.
- Header: date/time and back/voice buttons.

#### event_bus.py
- EventBus(EventDispatcher) with event on_events_changed.
- notify_events_changed() triggers updates across screens.

### 2) weather/ — Current Weather, Hourly and 6-day Forecast

#### weatherScreen.py
- Design:
  - Two symmetric cards: current conditions/hourly forecast and next six days.
  - Back and Voice buttons same size as main screen.
  - Day cards without border (rounded white background).
- Data:
  - OpenWeather for current condition (ES language).
  - Open-Meteo:
    - hourly: next 12 hours.
    - daily: next 6 days (tmin, tmax, precipitation probability).
- Refresh:
  - Background thread updates every 20 min (Clock + threading.Thread).
  - Maps icons (sun/night/cloud/rain/fog/snow/storm) to local images.
- TTS:
  - speak_window_info() narrates condition, current temperature, and min/max using pyttsx3.
- Utilities:
  - _render_hourly() and _render_daily() build layouts.
  - _map_icon_owm() and _map_icon_openmeteo() map codes to icons.
- Auxiliary: weather_today.json (stores observed min/max).

### 3) virtual_assistant/ — Speech → Intent → Action → Speech

#### Flow
1. recognizer.py (Vosk) listens and transcribes.
2. nlp_processor.py generates RoBERTa embeddings and passes them to the classifier.
3. actions.py executes the corresponding intent.
4. main_assistant.py orchestrates the full process and TTS.

#### actions.py
- Intent routing → methods:
  - show_events, start_call
  - get_date, get_time, get_weather, get_forecast
  - set_reminder, establish_reminder
  - get_news, get_recipe, tell_joke, greet, say_goodbye
- Extractors: reminder time, recipe name.
- UI integration: screen change and speech output.

#### intent_classifier.py
- Loads intent_dataset.json.
- Generates RoBERTa embeddings.
- Trains LogisticRegression.
- Saves models for offline inference.

#### nlp_processor.py
- Loads classifier, label encoder, and local RoBERTa model/tokenizer.
- Predicts intent.

#### recognizer.py
- Instantiates Vosk and sounddevice audio stream (16 kHz mono).
- Returns recognized text.

#### main_assistant.py
- Orchestrates full interaction with visual feedback and TTS fallback.

#### Data
- intent_dataset.json (sample phrases).

### 4) jokes/

#### jokesScreen.py
- Loads dataset mrm8488/CHISTES_spanish_jokes.
- Deferred loading (Clock) for smooth UI.
- Displays one random joke.
- Avoids repeating the previous one.

### 5) reminders/

#### reminders.py
- RecordatorioManager with persistent storage in reminders/recordatorios.json.
- Creates and schedules reminders with Clock.schedule_once.
- Reschedules pending reminders at startup.
- Announces reminders via app.speak_text and removes them after execution.

### 6) videocall/
- PyQt5/QWebEngine window loading project website.
- Default room and user: Maria.
- Fullscreen; exit button returns to main app.

### 7) mqtt_publisher.py
- MQTT CLI testing tool.
- Broker: broker.hivemq.com (port 1883).
- Topics: tarjeta and videollamada.
- Publishes manually for integration tests.

## Data / Log Files

| Path | Content |
|---|---|
| events/eventos_local.json | Local event cache |
| reminders/recordatorios.json | Pending reminders |
| weather/weather_today.json | Observed min/max of the day |

## Installation

1) Requirements
- Python 3.10+
- VLC installed
- PortAudio (for sounddevice/Vosk)
- Tkinter (for popups)
- Working webcam

2) Dependencies (UV)
- Use the project lock/dependency source:
  - `uv sync --project .`
- Optional explicit Python version:
  - `uv sync --project . --python 3.11`

3) Keys and Connection
Configure environment variables or .env file with:
MONGO_URI
OWM_API_KEY
NEWS_API_KEY
SPOONACULAR_API_KEY

4) Execution
- `uv run --project . mainApp.py`   # only UI (no camera)
- `uv run --project . mqtt_publisher.py`  # MQTT test
