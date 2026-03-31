# frontend-mueble/virtual_assistant/actions.py

from kivy.clock import Clock
from datetime import datetime
import os
import requests
from reminders.reminders import RecordatorioManager
from bs4 import BeautifulSoup
import re
from googletrans import Translator

HTTP_TIMEOUT = float(os.getenv("COBIEN_HTTP_TIMEOUT", "8"))
OWM_API_KEY = (os.getenv("OWM_API_KEY") or "").strip()
NEWS_API_KEY = (os.getenv("NEWS_API_KEY") or "").strip()
SPOONACULAR_API_KEY = (os.getenv("SPOONACULAR_API_KEY") or "").strip()


class ActionExecutor:
    def __init__(self, app_reference):
        self.app = app_reference  # Reference to the main Kivy app
        self.recordatorio_manager = RecordatorioManager(app_reference)

    def ejecutar(self, intencion, *args):
        acciones = {
            "abrir_radio": self.abrir_radio,
            "escuchar_radio": self.escuchar_radio,
            "ver_eventos": self.ver_eventos,
            "consultar_clima": self.consultar_clima,
            "iniciar_llamada": self.iniciar_llamada,
            "consultar_fecha": self.consultar_fecha,
            "consultar_hora": self.consultar_hora,
            "consultar_pronostico": self.consultar_pronostico,
            "configurar_recordatorio": self.configurar_recordatorio,
            "consultar_noticias": self.consultar_noticias,
            "consultar_receta": self.consultar_receta,
            "contar_chiste": self.contar_chiste,
            "saludar": self.saludar,
            "despedirse": self.despedirse,
            "volver_inicio": self.volver_inicio,
        }

        if intencion not in acciones:
            texto_a_decir = self._respuesta_sin_intencion(self.app.ultimo_texto)
        else:
            # Caso especial: escuchar_radio sin args
            if intencion == "escuchar_radio" and not args:
                if hasattr(self.app, "ultimo_texto"):
                    nombre_radio = self.extraer_nombre_radio(self.app.ultimo_texto)
                    texto_a_decir = acciones[intencion](nombre_radio)
                else:
                    texto_a_decir = "No se ha especificado una emisora para reproducir."

            # Caso especial: consultar_receta sin args
            elif intencion == "consultar_receta" and not args:
                receta = self.extraer_receta(self.app.ultimo_texto)
                texto_a_decir = acciones[intencion](receta)

            # Caso especial: configurar_recordatorio sin args
            elif intencion == "configurar_recordatorio" and not args:
                segundos, mensaje = self.extraer_recordatorio(self.app.ultimo_texto)
                texto_a_decir = acciones[intencion](segundos, mensaje)

            # General
            else:
                accion = acciones[intencion]
                texto_a_decir = accion(*args) if args else accion()

        return texto_a_decir

    # ------------------------------------------------------------
    # ACCIONES PRINCIPALES
    # ------------------------------------------------------------
    def abrir_radio(self):
        texto = "Abriendo la radio..."
        print(texto)
        Clock.schedule_once(lambda dt: self.app.cambiar_a_pantalla("radio"))
        return texto

    def escuchar_radio(self, nombre_radio):
        texto = f"Buscando la emisora {nombre_radio}..."
        print(texto)

        self.app.cambiar_a_pantalla("radio")
        Clock.schedule_once(lambda dt: self.reproducir_radio(nombre_radio), 1)
        return texto

    def reproducir_radio(self, nombre_radio):
        radio_screen = self.app.sm.get_screen("radio").children[0]  # Acceder al widget RadioScreen
        nombre_radio = nombre_radio.lower()
        for station_name, station_url in radio_screen.stations.items():
            if nombre_radio in station_name.lower():
                radio_screen.play_radio(station_url)
                texto = f"Reproduciendo {station_name}."
                print(texto)
                self.app.speak_text(texto)
                return
        texto = f"No he encontrado la emisora {nombre_radio}."
        print(texto)
        self.app.speak_text(texto)

    def extraer_nombre_radio(self, texto):
        emisoras = {
            "cadena cien": "Cadena 100",
            "los cuarenta": "Los 40",
            "rne": "RNE",
            "cope": "COPE",
            "npr": "National Public Radio",
            "cadena ser": "Cadena SER",
        }
        texto = texto.lower()
        for alias in emisoras:
            if alias in texto:
                return emisoras[alias]
        return texto

    def ver_eventos(self):
        texto = "Mostrando eventos..."
        print(texto)
        Clock.schedule_once(lambda dt: self.app.cambiar_a_pantalla("events"))
        return texto

    def iniciar_llamada(self):
        texto = "Iniciando videollamada..."
        print(texto)
        Clock.schedule_once(lambda dt: self.app.cambiar_a_pantalla("videocall"))
        return texto

    def consultar_fecha(self):
        hoy = datetime.now().strftime("%d/%m/%Y")
        texto = f"Hoy es {hoy}."
        print(texto)
        return texto

    def consultar_hora(self):
        hora_actual = datetime.now().strftime("%H:%M")
        texto = f"La hora actual es {hora_actual}."
        print(texto)
        return texto

    def consultar_clima(self):
        texto = "Consultando el clima..."
        print(texto)

        try:
            if not OWM_API_KEY:
                return "No he podido obtener el clima: falta la clave OWM_API_KEY."
            ciudad = "Bilbao"
            url = f"https://api.openweathermap.org/data/2.5/weather?q={ciudad}&appid={OWM_API_KEY}&units=metric&lang=es"
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

    def consultar_pronostico(self):
        texto = "Consultando el pronóstico del tiempo..."
        print(texto)

        try:
            if not OWM_API_KEY:
                return "No he podido obtener el pronóstico: falta la clave OWM_API_KEY."
            ciudad = "Bilbao"
            url = f"https://api.openweathermap.org/data/2.5/forecast?q={ciudad}&appid={OWM_API_KEY}&units=metric&lang=es"
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

    def configurar_recordatorio(self, tiempo_en_segundos, mensaje):
        texto = f"Recordatorio configurado para dentro de {tiempo_en_segundos} segundos."
        print(texto)

        def mostrar_recordatorio(dt):
            if hasattr(self.app, "speak_text"):
                self.app.speak_text(f"Recordatorio: {mensaje}")
            print(f"Recordatorio: {mensaje}")

        Clock.schedule_once(mostrar_recordatorio, tiempo_en_segundos)
        return texto

    def establecer_recordatorio(self, tiempo_en_segundos, mensaje):
        texto = self.recordatorio_manager.configurar_recordatorio(tiempo_en_segundos, mensaje)
        print(texto)
        return texto

    def extraer_recordatorio(self, texto):
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

    def consultar_noticias(self):
        texto = "Consultando las últimas noticias..."
        print(texto)

        try:
            if not NEWS_API_KEY:
                return "No he podido obtener noticias: falta la clave NEWS_API_KEY."
            url = f"https://newsapi.org/v2/top-headlines?country=es&category=general&apiKey={NEWS_API_KEY}"
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

    def extraer_consulta_general(self, texto):
        texto = texto.lower()
        expresiones = [
            r"quiero saber sobre", r"cu[aá]ntame sobre", r"d[ií]me sobre",
            r"expl[ií]came sobre", r"busca informaci[oó]n sobre",
            r"qu[ií]siera saber sobre", r"necesito saber sobre", r"consultar sobre", r"sobre"
        ]
        for patron in expresiones:
            texto = re.sub(patron, "", texto).strip()
        return texto

    def consultar_receta(self, receta):
        texto = f"Buscando receta para {receta}..."
        print(texto)

        try:
            if not SPOONACULAR_API_KEY:
                return "No he podido obtener la receta: falta la clave SPOONACULAR_API_KEY."
            url = f"https://api.spoonacular.com/recipes/complexSearch?query={receta}&number=1&apiKey={SPOONACULAR_API_KEY}"
            respuesta = requests.get(url, timeout=HTTP_TIMEOUT)
            respuesta.raise_for_status()
            datos = respuesta.json()

            if "results" in datos and len(datos["results"]) > 0:
                receta_id = datos["results"][0]["id"]
                receta_url = f"https://api.spoonacular.com/recipes/{receta_id}/information?apiKey={SPOONACULAR_API_KEY}"
                receta_resp = requests.get(receta_url, timeout=HTTP_TIMEOUT)
                receta_resp.raise_for_status()
                receta_info = receta_resp.json()

                nombre = receta_info.get("title", "Receta desconocida")
                instrucciones_html = receta_info.get("instructions", "No hay instrucciones disponibles.")
                instrucciones_limpias = BeautifulSoup(instrucciones_html, "html.parser").get_text()

                translator = Translator()
                nombre_es = translator.translate(nombre, src="en", dest="es").text
                instrucciones_es = translator.translate(instrucciones_limpias, src="en", dest="es").text

                texto = f"La receta para {nombre_es} es: {instrucciones_es}"
            else:
                texto = f"No he encontrado una receta para {receta}."
        except Exception as e:
            print(f"Error consultando receta: {e}")
            texto = "No he podido obtener la receta."
        print(texto)
        return texto

    def extraer_receta(self, texto):
        palabras_clave = ["una", "receta", "de", "para", "quiero", "hazme", "prepara", "pero", "busca", "quieres"]
        for palabra in palabras_clave:
            texto = texto.replace(palabra, "")
        return texto.strip()

    def contar_chiste(self):
        texto = "¿Por qué los pájaros no usan Facebook? ¡Porque ya tienen Twitter!"
        print(texto)
        return texto

    def saludar(self):
        texto = "¡Hola! ¿En qué puedo ayudarte hoy?"
        print(texto)
        return texto

    def despedirse(self):
        texto = "¡Hasta luego! Cuídate."
        print(texto)
        return texto

    def intencion_no_reconocida(self):
        texto = "Lo siento, no entendí la solicitud."
        print(texto)
        return texto

    def hablar(self, texto):
        if hasattr(self.app, "speak_text"):
            self.app.speak_text(texto)

    def _respuesta_sin_intencion(self, texto_usuario):
        if len(texto_usuario.strip()) < 5 or not any(c.isalpha() for c in texto_usuario):
            return "Lo siento, no entendí lo que dijiste. ¿Puedes repetirlo más claro?"
        else:
            return "Lo siento, todavía no sé cómo responder a eso. Estoy aprendiendo cada día."

    def volver_inicio(self):
        """Retourne au menu principal"""
        texto = "Volviendo al menú principal..."
        print(texto)
        Clock.schedule_once(lambda dt: self.app.cambiar_a_pantalla("main"))
        return texto
