import os
import queue
import sounddevice as sd
import json
from vosk import Model, KaldiRecognizer
import queue
import time

class SpeechRecognizer:
    def __init__(self, model_path=str, sample_rate=16000):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"No se encontró el modelo Vosk en {model_path}")
        
        self.model = Model(model_path)
        self.recognizer = KaldiRecognizer(self.model, sample_rate)
        self.q = queue.Queue()
        self.sample_rate = sample_rate

    def _clear_queue(self):
        """Méthode pour vider la file d'attente des sons parasites."""
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
    def listen_and_transcribe(self, timeout=15):
        print("Habla ahora...")
        self.recognizer.Reset()

        self._clear_queue()

        start_time = time.time()

        with sd.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=8000,
            dtype='int16',
            channels=1,
            callback=self._callback
        ):

            time.sleep(0.1)
            self._clear_queue()
            
            result = ""

            while True:
                if time.time() - start_time > timeout:
                    print("[VOSK] Timeout écoute")
                    break

                try:
                    data = self.q.get(timeout=0.2)
                except queue.Empty:
                    continue

                if self.recognizer.AcceptWaveform(data):
                    result_json = json.loads(self.recognizer.Result())
                    text = (result_json.get("text") or "").strip()

                    if len(text) < 2:
                        print("[VOSK] Résultat vide ignoré")
                        continue

                    result = text
                    break

        print("Texto detectado:", result)
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