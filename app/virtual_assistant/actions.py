"""Intent action handlers executed by the voice assistant.

This module maps normalized assistant intents to side effects such as
navigation, weather/news lookups, reminder scheduling, and conversational
responses.
"""

from kivy.clock import Clock
from datetime import datetime
import os
import requests
from reminders.reminders import RecordatorioManager
import re
from config_store import load_section
from typing import Any, Callable, Dict, Optional, Tuple

_SERVICES_CFG = load_section("services", {})
HTTP_TIMEOUT = float(_SERVICES_CFG.get("http_timeout_sec", os.getenv("COBIEN_HTTP_TIMEOUT", "8")))
OWM_API_KEY = (_SERVICES_CFG.get("owm_api_key", "") or "").strip()
NEWS_API_KEY = (_SERVICES_CFG.get("news_api_key", "") or "").strip()
OWM_CURRENT_URL = _SERVICES_CFG.get("openweather_current_url", "https://api.openweathermap.org/data/2.5/weather")
OWM_FORECAST_URL = _SERVICES_CFG.get("openweather_forecast_url", "https://api.openweathermap.org/data/2.5/forecast")
NEWS_API_URL = _SERVICES_CFG.get("news_api_url", "https://newsapi.org/v2/top-headlines")


class ActionExecutor:
    """Execute domain actions corresponding to assistant intents."""

    def __init__(self, app_reference: Any) -> None:
        """Initialize executor with a reference to the running app.

        Args:
            app_reference: Main Kivy application instance.
        """
        self.app = app_reference
        self.recordatorio_manager = RecordatorioManager(app_reference)

    def ejecutar(self, intencion: str, *args: Any) -> str:
        """Execute the action associated with an intent key.

        Args:
            intencion: Intent identifier resolved by NLP layer.
            *args: Optional action parameters.

        Returns:
            Spoken/returned response text for the executed action.
        """
        acciones = {
            "ver_eventos": self.ver_eventos,
            "consultar_clima": self.consultar_clima,
            "iniciar_llamada": self.iniciar_llamada,
            "consultar_fecha": self.consultar_fecha,
            "consultar_hora": self.consultar_hora,
            "consultar_pronostico": self.consultar_pronostico,
            "configurar_recordatorio": self.configurar_recordatorio,
            "consultar_noticias": self.consultar_noticias,
            "contar_chiste": self.contar_chiste,
            "saludar": self.saludar,
            "despedirse": self.despedirse,
            "volver_inicio": self.volver_inicio,
        }

        if intencion not in acciones:
            texto_a_decir = self._respuesta_sin_intencion(self.app.ultimo_texto)
        else:
            if intencion == "configurar_recordatorio" and not args:
                segundos, mensaje = self.extraer_recordatorio(self.app.ultimo_texto)
                texto_a_decir = acciones[intencion](segundos, mensaje)

            # General
            else:
                accion = acciones[intencion]
                texto_a_decir = accion(*args) if args else accion()

        return texto_a_decir

    def ver_eventos(self) -> str:
        """Navigate to the events screen."""
        texto = "Mostrando eventos..."
        print(texto)
        Clock.schedule_once(lambda dt: self.app.cambiar_a_pantalla("events"))
        return texto

    def iniciar_llamada(self) -> str:
        """Navigate to the video-call screen."""
        texto = "Iniciando videollamada..."
        print(texto)
        Clock.schedule_once(lambda dt: self.app.cambiar_a_pantalla("videocall"))
        return texto

    def consultar_fecha(self) -> str:
        """Return current local date."""
        hoy = datetime.now().strftime("%d/%m/%Y")
        texto = f"Hoy es {hoy}."
        print(texto)
        return texto

    def consultar_hora(self) -> str:
        """Return current local time."""
        hora_actual = datetime.now().strftime("%H:%M")
        texto = f"La hora actual es {hora_actual}."
        print(texto)
        return texto

    def consultar_clima(self) -> str:
        """Fetch and summarize current weather for the configured default city."""
        texto = "Consultando el clima..."
        print(texto)

        try:
            if not OWM_API_KEY:
                return "No he podido obtener el clima: falta la clave OWM_API_KEY."
            ciudad = "Bilbao"
            url = f"{OWM_CURRENT_URL}?q={ciudad}&appid={OWM_API_KEY}&units=metric&lang=es"
            respuesta = requests.get(url, timeout=HTTP_TIMEOUT)
            respuesta.raise_for_status()
            datos = respuesta.json()

            if datos.get("weather"):
                descripcion = datos["weather"][0]["description"]
                temperatura = datos["main"]["temp"]
                texto = f"El clima en {ciudad} es {descripcion} con una temperatura de {temperatura:.1f} grados."
            else:
                texto = "No he podido obtener el clima en este momento."
        except Exception as e:
            print(f"Error consultando el clima: {e}")
            texto = "No he podido obtener el clima."
        print(texto)
        return texto

    def consultar_pronostico(self) -> str:
        """Fetch and summarize weather forecast for the default city."""
        texto = "Consultando el pronóstico del tiempo..."
        print(texto)

        try:
            if not OWM_API_KEY:
                return "No he podido obtener el pronóstico: falta la clave OWM_API_KEY."
            ciudad = "Bilbao"
            url = f"{OWM_FORECAST_URL}?q={ciudad}&appid={OWM_API_KEY}&units=metric&lang=es"
            respuesta = requests.get(url, timeout=HTTP_TIMEOUT)
            respuesta.raise_for_status()
            datos = respuesta.json()

            if "list" in datos:
                pronostico = []
                for i in range(0, 24, 8):
                    fecha = datos["list"][i]["dt_txt"].split(" ")[0]
                    descripcion = datos["list"][i]["weather"][0]["description"]
                    temperatura = datos["list"][i]["main"]["temp"]
                    pronostico.append(f"{fecha}: {descripcion}, {temperatura}°C")

                texto = "El pronóstico para los próximos días es: " + ". ".join(pronostico)
            else:
                texto = "No he podido obtener el pronóstico del clima."
        except Exception as e:
            print(f"Error consultando el pronóstico: {e}")
            texto = "No he podido obtener el pronóstico del clima."
        print(texto)
        return texto

    def configurar_recordatorio(self, tiempo_en_segundos: int, mensaje: str) -> str:
        """Schedule an in-process reminder callback.

        Args:
            tiempo_en_segundos: Reminder delay in seconds.
            mensaje: Reminder text to be spoken/displayed.

        Returns:
            Confirmation message.
        """
        texto = f"Recordatorio configurado para dentro de {tiempo_en_segundos} segundos."
        print(texto)

        def mostrar_recordatorio(dt):
            if hasattr(self.app, "speak_text"):
                self.app.speak_text(f"Recordatorio: {mensaje}")
            print(f"Recordatorio: {mensaje}")

        Clock.schedule_once(mostrar_recordatorio, tiempo_en_segundos)
        return texto

    def establecer_recordatorio(self, tiempo_en_segundos: int, mensaje: str) -> str:
        """Delegate reminder persistence to ``RecordatorioManager``."""
        texto = self.recordatorio_manager.configurar_recordatorio(tiempo_en_segundos, mensaje)
        print(texto)
        return texto

    def extraer_recordatorio(self, texto: str) -> Tuple[int, str]:
        """Extract reminder delay and message from raw utterance text."""
        texto = texto.lower()
        match = re.search(r"(\d+)\s*(segundos?|minutos?)", texto)
        if match:
            cantidad = int(match.group(1))
            unidad = match.group(2)
            segundos = cantidad * 60 if "minuto" in unidad else cantidad
        else:
            segundos = 60
        mensaje = re.sub(r"con (un|una)? recordatorio (en|para)? ?\d* ?(segundos?|minutos?)? (para|por)?", "", texto).strip()
        if not mensaje:
            mensaje = "Tienes un recordatorio pendiente"
        return segundos, mensaje

    def consultar_noticias(self) -> str:
        """Fetch and summarize latest headlines."""
        texto = "Consultando las últimas noticias..."
        print(texto)

        try:
            if not NEWS_API_KEY:
                return "No he podido obtener noticias: falta la clave NEWS_API_KEY."
            url = f"{NEWS_API_URL}?country=es&category=general&apiKey={NEWS_API_KEY}"
            respuesta = requests.get(url, timeout=HTTP_TIMEOUT)
            respuesta.raise_for_status()
            datos = respuesta.json()

            if "articles" in datos and len(datos["articles"]) > 0:
                noticias = [a.get("title", "Sin título") for a in datos["articles"][:5]]
                texto = "Estas son las últimas noticias: " + ". ".join(noticias)
            else:
                texto = "No he podido obtener noticias en este momento."
        except Exception as e:
            print(f"Error consultando noticias: {e}")
            texto = "Ha ocurrido un error al obtener las noticias."
        print(texto)
        return texto

    def extraer_consulta_general(self, texto: str) -> str:
        """Normalize generic query utterances by removing prompt prefixes."""
        texto = texto.lower()
        expresiones = [
            r"quiero saber sobre", r"cu[aá]ntame sobre", r"d[ií]me sobre",
            r"expl[ií]came sobre", r"busca informaci[oó]n sobre",
            r"qu[ií]siera saber sobre", r"necesito saber sobre", r"consultar sobre", r"sobre"
        ]
        for patron in expresiones:
            texto = re.sub(patron, "", texto).strip()
        return texto

    def contar_chiste(self) -> str:
        """Return a static joke response."""
        texto = "¿Por qué los pájaros no usan Facebook? ¡Porque ya tienen Twitter!"
        print(texto)
        return texto

    def saludar(self) -> str:
        """Return a greeting response."""
        texto = "¡Hola! ¿En qué puedo ayudarte hoy?"
        print(texto)
        return texto

    def despedirse(self) -> str:
        """Return a farewell response."""
        texto = "¡Hasta luego! Cuídate."
        print(texto)
        return texto

    def intencion_no_reconocida(self) -> str:
        """Return fallback response for unknown intent."""
        texto = "Lo siento, no entendí la solicitud."
        print(texto)
        return texto

    def hablar(self, texto: str) -> None:
        """Speak text via app-level TTS method when available."""
        if hasattr(self.app, "speak_text"):
            self.app.speak_text(texto)

    def _respuesta_sin_intencion(self, texto_usuario: str) -> str:
        """Generate fallback response when no actionable intent exists."""
        if len(texto_usuario.strip()) < 5 or not any(c.isalpha() for c in texto_usuario):
            return "Lo siento, no entendí lo que dijiste. ¿Puedes repetirlo más claro?"
        else:
            return "Lo siento, todavía no sé cómo responder a eso. Estoy aprendiendo cada día."

    def volver_inicio(self) -> str:
        """Navigate back to the main screen."""
        texto = "Volviendo al menú principal..."
        print(texto)
        Clock.schedule_once(lambda dt: self.app.cambiar_a_pantalla("main"))
        return texto
