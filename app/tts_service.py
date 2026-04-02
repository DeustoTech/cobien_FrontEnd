import os
import threading
import subprocess
import tempfile
import shutil
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
        self._piper_bin_cache = None

    def _ensure_engine(self):
        if pyttsx3 is None:
            return None
        if self._engine is None:
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", DEFAULT_RATE)
            self._engine.setProperty("volume", DEFAULT_VOLUME)
        return self._engine

    def _load_runtime_tts_config(self):
        """Read current TTS settings from unified config at call time."""
        services_cfg = load_section("services", {})
        engine = (services_cfg.get("tts_engine", "pyttsx3") or "pyttsx3").strip().lower()
        rate = int(services_cfg.get("tts_rate", os.getenv("COBIEN_TTS_RATE", str(DEFAULT_RATE))))
        volume = float(services_cfg.get("tts_volume", os.getenv("COBIEN_TTS_VOLUME", str(DEFAULT_VOLUME))))
        piper_bin = (services_cfg.get("tts_piper_bin", "") or "").strip()
        piper_model_es = (services_cfg.get("tts_piper_model_es", "") or "").strip()
        piper_model_fr = (services_cfg.get("tts_piper_model_fr", "") or "").strip()
        return engine, rate, volume, piper_bin, piper_model_es, piper_model_fr

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

        engine_name, rate, volume, piper_bin, piper_model_es, piper_model_fr = self._load_runtime_tts_config()

        if engine_name == "piper":
            if self._speak_with_piper(
                text,
                language=language,
                configured_bin=piper_bin,
                model_es=piper_model_es,
                model_fr=piper_model_fr,
            ):
                return True
            print("[TTS] Piper selected but unavailable/misconfigured. Falling back to pyttsx3.")

        engine = self._ensure_engine()
        if engine is None:
            print(f"[TTS fallback] {text}")
            return False

        with self._lock:
            try:
                engine.setProperty("rate", rate)
                engine.setProperty("volume", volume)
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

    def _resolve_piper_bin(self, configured_bin=""):
        if self._piper_bin_cache:
            return self._piper_bin_cache
        candidates = []
        if configured_bin:
            candidates.append(configured_bin)
        candidates.extend([
            "piper",
            os.path.expanduser("~/.local/bin/piper"),
            "/usr/bin/piper",
            "/usr/local/bin/piper",
        ])
        for candidate in candidates:
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                self._piper_bin_cache = candidate
                return candidate
            if "/" not in candidate:
                found = shutil.which(candidate)
                if found:
                    self._piper_bin_cache = found
                    return found
        return None

    def _resolve_piper_model(self, language, model_es="", model_fr=""):
        model = model_fr if language == "fr" else model_es
        if model and os.path.exists(model):
            return model
        return None

    def _speak_with_piper(self, text, language="es", configured_bin="", model_es="", model_fr=""):
        piper_bin = self._resolve_piper_bin(configured_bin=configured_bin)
        model_path = self._resolve_piper_model(language, model_es=model_es, model_fr=model_fr)
        if not piper_bin or not model_path:
            if not piper_bin:
                print("[TTS] Piper binary not found.")
            if not model_path:
                print(f"[TTS] Piper model missing for language={language}.")
            return False
        if not shutil.which("aplay"):
            print("[TTS] aplay command not available; cannot play Piper WAV output.")
            return False

        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                wav_path = tmp_file.name
            cmd = [piper_bin, "--model", model_path, "--output_file", wav_path]
            proc = subprocess.run(cmd, input=text.encode("utf-8"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            if proc.returncode != 0:
                return False
            play = subprocess.run(["aplay", "-q", wav_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            return play.returncode == 0
        except Exception:
            return False
        finally:
            try:
                if 'wav_path' in locals() and os.path.exists(wav_path):
                    os.remove(wav_path)
            except Exception:
                pass


tts_service = TTSService()
