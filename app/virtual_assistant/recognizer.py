import os
import queue
import sounddevice as sd
import json
import audioop
from vosk import Model, KaldiRecognizer
import time


def select_input_device(preferred_device=None):
    """Resolve a valid input device, preferring persisted names when possible."""
    try:
        devices = sd.query_devices()
    except Exception as exc:
        print(f"[ASR] Unable to list audio devices: {exc}")
        return None, ""

    def is_valid_input(index):
        try:
            return devices[index]["max_input_channels"] > 0
        except Exception:
            return False

    if isinstance(preferred_device, int) and is_valid_input(preferred_device):
        return preferred_device, devices[preferred_device]["name"]

    if isinstance(preferred_device, str) and preferred_device.strip():
        preferred = preferred_device.strip().lower()
        for idx, device in enumerate(devices):
            if device["max_input_channels"] <= 0:
                continue
            name = device["name"].strip()
            if name.lower() == preferred or preferred in name.lower():
                return idx, name

    try:
        default_input = sd.default.device[0]
    except Exception:
        default_input = None

    if isinstance(default_input, int) and default_input >= 0 and is_valid_input(default_input):
        return default_input, devices[default_input]["name"]

    preferred_keywords = (
        "digital microphone",
        "digital mic",
        "sof-hda",
        "microphone",
        "mic",
    )
    for keyword in preferred_keywords:
        for idx, device in enumerate(devices):
            if device["max_input_channels"] <= 0:
                continue
            name = device["name"].strip()
            if keyword in name.lower():
                return idx, name

    for idx, device in enumerate(devices):
        if device["max_input_channels"] > 0:
            return idx, device["name"]

    return None, ""

class SpeechRecognizer:
    def __init__(self, model_path=str, sample_rate=16000, input_device=None):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"No se encontró el modelo Vosk en {model_path}")
        
        self.model = Model(model_path)
        self.recognizer = KaldiRecognizer(self.model, sample_rate)
        self.q = queue.Queue()
        self.sample_rate = sample_rate
        self.input_device, self.input_device_name = select_input_device(input_device)
        print(f"[ASR] Input device: {self.input_device_name or 'default'}")

    def _clear_queue(self):
        """Clear queued audio frames."""
        while not self.q.empty():
            try:
                self.q.get_nowait()
            except queue.Empty:
                break

    def _callback(self, indata, frames, time, status):
        if status:
            print("Status:", status)
        self.q.put(bytes(indata))


    # Version non blocking of liste_and_transcribe
    def listen_and_transcribe(self, timeout=15, stop_event=None, level_callback=None):
        print("[ASR] Speak now...")
        self.recognizer.Reset()

        self._clear_queue()

        start_time = time.time()

        with sd.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=8000,
            dtype='int16',
            channels=1,
            device=self.input_device,
            callback=self._callback
        ):

            if stop_event is not None and stop_event.is_set():
                print("[VOSK] Cancelled before warmup")
                return None

            time.sleep(0.1)
            self._clear_queue()
            
            result = ""

            while True:
                if stop_event is not None and stop_event.is_set():
                    print("[VOSK] Cancelled")
                    break

                if time.time() - start_time > timeout:
                    print("[VOSK] Listening timeout")
                    break

                try:
                    data = self.q.get(timeout=0.2)
                except queue.Empty:
                    if stop_event is not None and stop_event.is_set():
                        print("[VOSK] Cancelled while waiting for audio")
                        break
                    continue

                if callable(level_callback):
                    try:
                        rms = audioop.rms(data, 2)
                        # Empirical normalization for 16-bit mono stream
                        norm = min(1.0, float(rms) / 3500.0)
                        level_callback(norm)
                    except Exception:
                        pass

                if self.recognizer.AcceptWaveform(data):
                    result_json = json.loads(self.recognizer.Result())
                    text = (result_json.get("text") or "").strip()

                    if len(text) < 2:
                        print("[VOSK] Ignoring empty result")
                        continue

                    result = text
                    break

        print("[ASR] Detected text:", result)
        return result if result else None

    """
    def listen_and_transcribe(self, timeout=15):
        print("Habla ahora...")
        start_time = time.time()

        with sd.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=8000,
            dtype='int16',
            channels=1,
            callback=self._callback
        ):
            result = ""

            while True:
                # timeout global de sécurité
                if time.time() - start_time > timeout:
                    print("[VOSK] Timeout écoute")
                    break

                try:
                    # NE BLOQUE PLUS INFINIMENT
                    data = self.q.get(timeout=0.2)
                except queue.Empty:
                    continue

                if self.recognizer.AcceptWaveform(data):
                    result_json = json.loads(self.recognizer.Result())
                    result = result_json.get("text", "")
                    break

        print("Texto detectado:", result)
        return result
    """
    """
    def listen_and_transcribe(self):
        print("Habla ahora...")
        with sd.RawInputStream(samplerate=self.sample_rate, blocksize=8000, dtype='int16',
                               channels=1, callback=self._callback):
            result = ""
            while True:
                data = self.q.get()
                if self.recognizer.AcceptWaveform(data):
                    result_json = json.loads(self.recognizer.Result())
                    result = result_json.get("text", "")
                    break
        print("Texto detectado:", result)
        return result
    """
