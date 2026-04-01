import os
import threading
from config_store import load_section


try:
    import pyttsx3
except Exception:
    pyttsx3 = None


_SERVICES_CFG = load_section("services", {})
DEFAULT_RATE = int(_SERVICES_CFG.get("tts_rate", os.getenv("COBIEN_TTS_RATE", "155")))
DEFAULT_VOLUME = float(_SERVICES_CFG.get("tts_volume", os.getenv("COBIEN_TTS_VOLUME", "0.85")))


class TTSService:
    def __init__(self):
        self._engine = None
        self._lock = threading.Lock()
        self._voice_cache = {}

    def _ensure_engine(self):
        if pyttsx3 is None:
            return None
        if self._engine is None:
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", DEFAULT_RATE)
            self._engine.setProperty("volume", DEFAULT_VOLUME)
        return self._engine

    def _voice_matches(self, voice, language):
        targets = ("french", "fr", "fr-fr") if language == "fr" else ("spanish", "es", "es-es")
        haystack = [getattr(voice, "id", ""), getattr(voice, "name", "")]
        try:
            haystack.extend(
                item.decode("utf-8", errors="ignore") if isinstance(item, bytes) else str(item)
                for item in getattr(voice, "languages", []) or []
            )
        except Exception:
            pass
        blob = " ".join(haystack).lower()
        return any(target in blob for target in targets)

    def _select_voice(self, engine, language):
        cached = self._voice_cache.get(language)
        if cached:
            try:
                engine.setProperty("voice", cached)
                return
            except Exception:
                self._voice_cache.pop(language, None)

        for voice in engine.getProperty("voices"):
            if self._voice_matches(voice, language):
                engine.setProperty("voice", voice.id)
                self._voice_cache[language] = voice.id
                return

    def speak_sync(self, text, language="es"):
        if not text:
            return False

        engine = self._ensure_engine()
        if engine is None:
            print(f"[TTS fallback] {text}")
            return False

        with self._lock:
            try:
                self._select_voice(engine, language)
                try:
                    engine.stop()
                except Exception:
                    pass
                engine.say(text)
                engine.runAndWait()
                return True
            except Exception as exc:
                print(f"[TTS ERROR] {exc}")
                print(text)
                return False


tts_service = TTSService()
