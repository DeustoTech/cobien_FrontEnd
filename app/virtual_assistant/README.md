# Virtual Assistant Module

## Overview

The `virtual_assistant` package implements the voice interaction pipeline used
by the CoBien app:

1. Capture microphone audio with Vosk (`recognizer.py`).
2. Match recognized text to navigation commands (`commands.py`).
3. Execute intent actions and side effects (`actions.py`).
4. Orchestrate complete user flow and UI feedback (`main_assistant.py`).

## Files

- `main_assistant.py`: Runtime orchestrator for listen/speak/navigation flow.
- `recognizer.py`: Audio device selection and speech-to-text capture.
- `commands.py`: Keyword dictionary and command matching.
- `actions.py`: Intent action implementations (weather, news, reminders, etc.).
- `intent_dataset.json`: Dataset used by legacy/auxiliary intent logic.
- `vosk_models/`: Offline ASR models.

## Runtime Responsibilities

- Provide low-latency voice command handling from any screen that calls
  `app.start_assistant()`.
- Keep language-aware ASR model selection synchronized with app config.
- Route recognized commands into app navigation events.
- Generate spoken feedback via app TTS (`tts_service` fallback).

## Known Technical Debt / Bad Practices

- The module mixes multiple assistant paradigms (keyword routing, intent/action
  routing, legacy commented code), which increases maintenance complexity.
- `actions.py` contains high coupling to network services and hardcoded defaults
  (for example fixed city `"Bilbao"`), reducing configurability and testability.
- Error handling is mostly `print`-based and lacks centralized structured logs.
- Large commented-out legacy blocks in `main_assistant.py` and
  `recognizer.py` reduce readability and obscure active behavior.
- External API calls and translations are executed synchronously inside action
  methods, which may block responsiveness under slow networks.
