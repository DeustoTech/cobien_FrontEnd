# frontend-mueble/virtual_assistant/main_assistant.py

from virtual_assistant.recognizer import SpeechRecognizer
from virtual_assistant.nlp_processor import IntentClassifier
from virtual_assistant.actions import ActionExecutor

# Fallback a TTS local si la app no tiene speak_text
try:
    import pyttsx3
except Exception:
    pyttsx3 = None


class AssistantOrchestrator:
    def __init__(self, app_reference):
        # Componentes del asistente
        self.recognizer = SpeechRecognizer()
        self.classifier = IntentClassifier()
        self.executor = ActionExecutor(app_reference)

        # Referencia a la app principal (para speak_text y result_label)
        self.app = app_reference

        # Motor TTS de respaldo
        self._tts_engine = None

    # -------------------------
    # Utilidades internas
    # -------------------------
    def _speak(self, text: str):
        """
        Habla usando app.speak_text si existe; si no, usa pyttsx3.
        Si todo falla, imprime el texto.
        """
        if not text:
            return

        # Si la app tiene método speak_text
        if hasattr(self.app, "speak_text") and callable(getattr(self.app, "speak_text")):
            try:
                self.app.speak_text(text)
                return
            except Exception as e:
                print(f"[WARN] speak_text falló: {e}")

        # Si no, intentar pyttsx3
        if pyttsx3 is not None:
            try:
                if self._tts_engine is None:
                    self._tts_engine = pyttsx3.init()
                self._tts_engine.say(text)
                self._tts_engine.runAndWait()
                return
            except Exception as e:
                print(f"[WARN] pyttsx3 falló: {e}")

        # Último recurso: mostrar por consola
        print(f"[TTS fallback] {text}")

    def _actualizar_label(self, texto: str):
        """Actualiza la etiqueta result_label si existe."""
        if hasattr(self.app, "result_label"):
            try:
                self.app.result_label.text = texto
            except Exception as e:
                print(f"[WARN] No se pudo actualizar result_label: {e}")

    # -------------------------
    # Flujo principal
    # -------------------------
    def start(self):
        """
        Flujo completo: escuchar → interpretar → ejecutar → responder
        """
        try:
            # Feedback inicial para el usuario
            self._actualizar_label("Escuchando…")
            self._speak("Hola, ¿en qué puedo ayudarte?")

            # Escucha y transcribe
            texto = self.recognizer.listen_and_transcribe()
            print(f"Texto detectado: {texto}")
            self._actualizar_label(f"Has dicho: {texto}")

            # Guardar texto para posibles referencias
            try:
                self.app.ultimo_texto = texto
            except Exception:
                pass

            # Clasifica la intención
            intencion = self.classifier.predecir_intencion(texto)
            print(f"Intención detectada: {intencion}")

            # Ejecuta la acción correspondiente
            respuesta = self.executor.ejecutar(intencion)

            # Si hay texto devuelto, lo decimos y mostramos
            if isinstance(respuesta, str) and respuesta.strip():
                self._speak(respuesta)
                self._actualizar_label(respuesta)

        except Exception as e:
            print(f"Error en el asistente: {e}")
            self._actualizar_label("Ha ocurrido un error")
            self._speak("Lo siento, ha ocurrido un error")
