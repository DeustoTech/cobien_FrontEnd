import os
import queue
import sounddevice as sd
import json
from vosk import Model, KaldiRecognizer

class SpeechRecognizer:
    def __init__(self, model_path="virtual_assistant/vosk_models/vosk-model-small-es-0.42", sample_rate=16000):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"No se encontró el modelo Vosk en {model_path}")
        
        self.model = Model(model_path)
        self.recognizer = KaldiRecognizer(self.model, sample_rate)
        self.q = queue.Queue()
        self.sample_rate = sample_rate

    def _callback(self, indata, frames, time, status):
        if status:
            print("Status:", status)
        self.q.put(bytes(indata))

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
