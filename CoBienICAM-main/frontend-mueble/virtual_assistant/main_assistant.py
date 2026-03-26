# frontend-mueble/virtual_assistant/main_assistant.py

from virtual_assistant.recognizer import SpeechRecognizer
from virtual_assistant.nlp_processor import IntentClassifier
from virtual_assistant.actions import ActionExecutor
from kivy.uix.screenmanager import Screen
############# SIMONA
from virtual_assistant.commands import match_command
from kivy.clock import Clock
import subprocess
import tempfile
import os
import threading
from translation import _
import time


#############

# Fallback a TTS local si la app no tiene speak_text
try:
    import pyttsx3
except Exception:
    pyttsx3 = None


class AssistantOrchestrator:
    def __init__(self, app_reference):
        # Componentes del asistente
        self.recognizer = None
        self.app = app_reference
        self._recognizer_path = self._get_model_path()
        self._recognizer_language = self.app.cfg.data.get("language", "es")
        self._stop_event = threading.Event()

        # AJOUT : Charger le modèle en arrière-plan immédiatement
        threading.Thread(target=self._preload_model, daemon=True).start()
        
        # On évite le chargement des modèles vosk au démarrage
        #self.recognizer = SpeechRecognizer(app_path)
        self.classifier = IntentClassifier()
        self.executor = ActionExecutor(app_reference)

        # Motor TTS de respaldo
        self._tts_engine = None

        self._running = False
        self._listening = False

    # -------------------------
    # Utilidades internas
    # -------------------------
    def _get_model_path(self):
        language = self.app.cfg.data.get("language", "es")
        if language == "es":
            return "virtual_assistant/vosk_models/vosk-model-small-es-0.42"
        return "virtual_assistant/vosk_models/vosk-model-small-fr-0.22"

    def _ensure_recognizer(self):
        language = self.app.cfg.data.get("language", "es")
        desired_path = self._get_model_path()
        if (
            self.recognizer is None
            or self._recognizer_language != language
            or self._recognizer_path != desired_path
        ):
            self._recognizer_path = desired_path
            self._recognizer_language = language
            self.recognizer = SpeechRecognizer(
                desired_path,
                input_device=self.app.cfg.get_microphone_device(),
            )
            if (
                self.recognizer.input_device_name
                and self.recognizer.input_device_name != self.app.cfg.get_microphone_device()
            ):
                self.app.cfg.set_microphone_device(self.recognizer.input_device_name)

    def _preload_model(self):
        print("[ASR] Pré-chargement du modèle Vosk...")
        self._ensure_recognizer()
        print("[ASR] Modèle prêt !")


    """
    def _speak(self, text: str):
        
        #Habla usando app.speak_text si existe; si no, usa pyttsx3.
        #Si todo falla, imprime el texto.
        
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
    """

    """
    ########## SIMONA TEST 1
    def _speak(self, text: str):
        if not text:
            return

        # Prefer app TTS
        if hasattr(self.app, "speak_text") and callable(self.app.speak_text):
            try:
                self.app.speak_text(text)
                return
            except Exception as e:
                print(f"[WARN] speak_text failed: {e}")

        # pyttsx3 fallback
        if pyttsx3 is None:
            print(text)
            return

        try:
            if self._tts_engine is None:
                self._tts_engine = pyttsx3.init()

                # Select voice based on app language
                lang = self.app.cfg.data["language"]
                for v in self._tts_engine.getProperty("voices"):
                    if lang.encode() in v.languages:
                        self._tts_engine.setProperty("voice", v.id)
                        break

            self._tts_engine.say(text)
            self._tts_engine.runAndWait()

        except Exception as e:
            print(f"[TTS fallback] {text} ({e})")
    ##################
    """
    def speak(self, text):
        self._speak(text)

    def listen(self, prompt: str) -> str | None:
        # empêche double écoute
        if self._listening or self._running:
            print("[ASR] écoute déjà en cours → ignoré")
            return None

        self._listening = True
        try:
            self._ensure_recognizer()
            time.sleep(0.2)
            
            self.speak(prompt)         

            return self.recognizer.listen_and_transcribe(stop_event=self._stop_event)
        finally:
            self._listening = False


    """
    def listen(self, prompt: str) -> str | None:
        self.speak(prompt)

        if self._needs_post_tts_delay:
            import time
            time.sleep(0.6)
            self._needs_post_tts_delay = False

        if self.recognizer is None:
            self.recognizer = SpeechRecognizer(self._recognizer_path)
        
        # Warm-up micro UNE SEULE FOIS
        if not self._asr_warmed_up:
            try:
                self.recognizer.listen_and_transcribe(timeout=0.5)
            except Exception:
                pass
            self._asr_warmed_up = True

        return self.recognizer.listen_and_transcribe()
    """

    def _speak(self, text: str):
        if not text:
            return

        # Prefer app TTS if available
        if hasattr(self.app, "speak_text") and callable(self.app.speak_text):
            try:
                self.app.speak_text(text)
                return
            except Exception:
                pass

        # Pico TTS fallback (BEST)
        try:
            lang = self.app.cfg.data["language"]
            pico_lang = "fr-FR" if lang == "fr" else "es-ES"

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                wav_path = f.name

            subprocess.run(
                ["pico2wave", "-l", pico_lang, "-w", wav_path, text],
                check=True
            )
            subprocess.run(["aplay", wav_path], check=True)

            os.remove(wav_path)

            self._needs_post_tts_delay = True


        except Exception as e:
            print(f"[TTS ERROR] {e}")
            print(text)


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
        if getattr(self, "_running", False):
            return
        self._ensure_recognizer()
        self._stop_event.clear()
        self._running = True

        threading.Thread(
            target=self._run_assistant,
            daemon=True
        ).start()

    def cancel(self):
        print("[ASR] Cancel requested")
        self._stop_event.set()
        self._running = False
        self._listening = False

    def _run_assistant(self):
        try:
            # Feedback initial pour l’utilisateur
            #self._actualizar_label("Escuchando…")
            language = self.app.cfg.data["language"]

            self._speak(_("Hola, ¿en qué puedo ayudarte"))
            """
            if language == "es":
                self._speak("Hola, ¿en qué puedo ayudarte")
            else:
                self._speak("Bonjour, comment puis-je vous aider")
            """

            # BLOQUANT mais dans un thread
            self._listening = True
            texto = self.recognizer.listen_and_transcribe(stop_event=self._stop_event)
            self._listening = False
            if self._stop_event.is_set():
                self._actualizar_label(_("Asistente cancelado"))
                return
            if not texto:
                self._actualizar_label(_("No he entendido"))
                self._speak(_("No he reconocido el comando"))
                return
            print(f"Texto detectado: {texto}")

            self._actualizar_label(f"Has dicho: {texto}")

            try:
                self.app.ultimo_texto = texto
            except Exception:
                pass

            # Commandes par mots-clés
            nav_target = match_command(texto)

            if nav_target:
                Clock.schedule_once(lambda dt, t=nav_target, txt=texto: self.app.on_nav(t, source="vocal_assistant", recognized_text=txt))
                self._speak(_("De acuerdo"))
                """
                if language == "es":
                    self._speak("De acuerdo")
                else:
                    self._speak("D'accord, j'ai compris")
                """
                self._actualizar_label("OK")
            else:
                self._speak(_("No he reconocido el comando"))
                """
                if language == "es":
                    self._speak("No he reconocido el comando")
                else:
                    self._speak("Je n'ai pas compris")
                """
                self._actualizar_label("Comando no reconocido")
            
        except Exception as e:
            print(f"Error en el asistente: {e}")
            self._actualizar_label("Ha ocurrido un error")
            self._speak(_("Lo siento, ha ocurrido un error"))
        finally:
            self._running = False
            self._listening = False
            self._stop_event.clear()

    """
    def start(self):
        
        #Flujo completo: escuchar → interpretar → ejecutar → responder
        
    
        try:
            # Feedback inicial para el usuario
            self._actualizar_label("Escuchando…")
            language = self.app.cfg.data["language"]
            if language == "es" :
                self._speak("Hola, ¿en qué puedo ayudarte")
            else :
                self._speak("Bonjour, comment puis je vous aider")

            # Escucha y transcribe
            texto = self.recognizer.listen_and_transcribe()
            print(f"Texto detectado: {texto}")
            self._actualizar_label(f"Has dicho: {texto}")

            # Guardar texto para posibles referencias
            try:
                self.app.ultimo_texto = texto
            except Exception:
                pass

            ####################SIMONA
        
            # Keyword-based command matching (NEW)
            from virtual_assistant.commands import match_command
            nav_target = match_command(texto)

            # Execute action
            if nav_target:
                Clock.schedule_once(lambda dt, t=nav_target, txt=texto: self.app.on_nav(t, source="vocal_assistant", recognized_text=txt))
                language = self.app.cfg.data["language"]
                if language == "es" :
                    self._speak("De acuerdo")
                else :
                    self._speak("D'accord, j'ai compris")
                self._actualizar_label("OK")
            else:
                language = self.app.cfg.data["language"]
                if language == "es" :
                    self._speak("No he reconocido el comando")
                else :
                    self._speak("Je n'ai pas compris")
                self._actualizar_label("Comando no reconocido")

            ############################
            
            # Clasifica la intención
            #intencion = self.classifier.predecir_intencion(texto)
            #print(f"Intención detectada: {intencion}")

            # Ejecuta la acción correspondiente
            #respuesta = self.executor.ejecutar(intencion)

            # Si hay texto devuelto, lo decimos y mostramos
            #if isinstance(respuesta, str) and respuesta.strip():
            #    self._speak(respuesta)
            #    self._actualizar_label(respuesta)
            
        except Exception as e:
            print(f"Error en el asistente: {e}")
            self._actualizar_label("Ha ocurrido un error")
            self._speak("Lo siento, ha ocurrido un error")
    """
