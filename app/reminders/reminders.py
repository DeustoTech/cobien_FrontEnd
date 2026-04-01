import json
import os
from kivy.clock import Clock
from datetime import datetime, timedelta

class RecordatorioManager:
    def __init__(self, app_reference):
        self.app = app_reference
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.recordatorios_file = os.path.join(base_dir, "recordatorios.json")
        print(f"Archivo de recordatorios: {self.recordatorios_file}")
        self.cargar_recordatorios_pendientes()

    def configurar_recordatorio(self, tiempo_en_segundos, mensaje):
        ahora = datetime.now()
        hora_recordatorio = ahora + timedelta(seconds=tiempo_en_segundos)
        recordatorio = {
            "mensaje": mensaje,
            "hora": hora_recordatorio.strftime("%Y-%m-%d %H:%M:%S")
        }

        self.guardar_recordatorio(recordatorio)

        Clock.schedule_once(lambda dt: self.mostrar_recordatorio(mensaje), tiempo_en_segundos)
        print(f"Recordatorio configurado: '{mensaje}' en {tiempo_en_segundos} segundos.")
        return f"Recordatorio configurado: '{mensaje}' en {tiempo_en_segundos} segundos."

    def mostrar_recordatorio(self, mensaje):
        if hasattr(self.app, "speak_text"):
            self.app.speak_text(f"Recordatorio: {mensaje}")
        print(f"Recordatorio: {mensaje}")
        self.eliminar_recordatorio(mensaje)

    def guardar_recordatorio(self, recordatorio):
        try:
            recordatorios = self.cargar_recordatorios()
            recordatorios.append(recordatorio)

            with open(self.recordatorios_file, "w", encoding="utf-8") as f:
                json.dump(recordatorios, f, ensure_ascii=False, indent=4)

            print("Recordatorio guardado correctamente.")
        except Exception as e:
            print(f"Error al guardar recordatorio: {e}")

    def cargar_recordatorios(self):
        if os.path.exists(self.recordatorios_file):
            try:
                with open(self.recordatorios_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error al cargar recordatorios: {e}")
                return []
        return []

    def cargar_recordatorios_pendientes(self):
        recordatorios = self.cargar_recordatorios()
        ahora = datetime.now()

        for recordatorio in recordatorios:
            hora_recordatorio = datetime.strptime(recordatorio["hora"], "%Y-%m-%d %H:%M:%S")
            if hora_recordatorio > ahora:
                segundos_restantes = (hora_recordatorio - ahora).total_seconds()
                Clock.schedule_once(lambda dt: self.mostrar_recordatorio(recordatorio["mensaje"]), segundos_restantes)
            else:
                self.eliminar_recordatorio(recordatorio["mensaje"])

    def eliminar_recordatorio(self, mensaje):
        recordatorios = self.cargar_recordatorios()
        recordatorios = [r for r in recordatorios if r["mensaje"] != mensaje]

        try:
            with open(self.recordatorios_file, "w", encoding="utf-8") as f:
                json.dump(recordatorios, f, ensure_ascii=False, indent=4)
            print(f"Recordatorio eliminado: {mensaje}")
        except Exception as e:
            print(f"Error al eliminar recordatorio: {e}")
