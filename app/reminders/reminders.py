"""Reminder scheduling and persistence utilities for the CoBien app.

This module encapsulates reminder lifecycle management:

1. Persist reminders to a local JSON file.
2. Schedule reminder callbacks with the Kivy clock.
3. Restore pending reminders after app restart.
4. Trigger speech feedback when a reminder expires.

The manager is intentionally simple and file-based, so it can run offline and
without external services.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List

from kivy.clock import Clock


ReminderEntry = Dict[str, str]

class RecordatorioManager:
    """Manage local reminders backed by a JSON file.

    The class provides high-level methods to create reminders, persist them,
    reschedule pending reminders during startup, and remove reminders once
    executed.
    """

    def __init__(self, app_reference: Any) -> None:
        """Initialize the reminder manager and reschedule pending reminders.

        Args:
            app_reference (Any): Running app instance. If it exposes
                ``speak_text(str)``, reminders are announced by voice.

        Returns:
            None.

        Raises:
            ValueError: If a persisted reminder contains an invalid datetime
                format while loading pending reminders.
        """
        self.app = app_reference
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.recordatorios_file = os.path.join(base_dir, "recordatorios.json")
        print(f"Archivo de recordatorios: {self.recordatorios_file}")
        self.cargar_recordatorios_pendientes()

    def configurar_recordatorio(self, tiempo_en_segundos: float, mensaje: str) -> str:
        """Create, persist, and schedule a new reminder.

        Args:
            tiempo_en_segundos (float): Delay in seconds before reminder
                execution.
            mensaje (str): Reminder message shown and spoken when fired.

        Returns:
            str: Human-readable confirmation message.

        Raises:
            OverflowError: If adding the delay to the current datetime
                overflows platform datetime limits.

        Examples:
            >>> mgr = RecordatorioManager(app_reference)
            >>> mgr.configurar_recordatorio(30, "Tomar medicación")
            "Recordatorio configurado: 'Tomar medicación' en 30 segundos."
        """
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

    def mostrar_recordatorio(self, mensaje: str) -> None:
        """Execute one reminder: announce it and remove it from persistence.

        Args:
            mensaje (str): Reminder message to present.

        Returns:
            None.

        Raises:
            No exception is propagated by this method itself. Downstream
                persistence errors are handled in ``eliminar_recordatorio``.

        Examples:
            >>> mgr.mostrar_recordatorio("Llamar a la familia")
        """
        if hasattr(self.app, "speak_text"):
            self.app.speak_text(f"Recordatorio: {mensaje}")
        print(f"Recordatorio: {mensaje}")
        self.eliminar_recordatorio(mensaje)

    def guardar_recordatorio(self, recordatorio: ReminderEntry) -> None:
        """Append a reminder entry to the JSON storage file.

        Args:
            recordatorio (ReminderEntry): Reminder payload with keys:
                ``mensaje`` and ``hora``.

        Returns:
            None.

        Raises:
            No exception is propagated. File and JSON errors are logged.

        Examples:
            >>> mgr.guardar_recordatorio({
            ...     "mensaje": "Beber agua",
            ...     "hora": "2026-04-02 14:30:00",
            ... })
        """
        try:
            recordatorios = self.cargar_recordatorios()
            recordatorios.append(recordatorio)

            with open(self.recordatorios_file, "w", encoding="utf-8") as f:
                json.dump(recordatorios, f, ensure_ascii=False, indent=4)

            print("Recordatorio guardado correctamente.")
        except Exception as e:
            print(f"Error al guardar recordatorio: {e}")

    def cargar_recordatorios(self) -> List[ReminderEntry]:
        """Load all persisted reminders from local JSON storage.

        Returns:
            List[ReminderEntry]: List of stored reminders. Returns an empty list
            when the file does not exist or cannot be parsed.

        Raises:
            No exception is propagated. File and JSON errors are logged.

        Examples:
            >>> reminders = mgr.cargar_recordatorios()
            >>> isinstance(reminders, list)
            True
        """
        if os.path.exists(self.recordatorios_file):
            try:
                with open(self.recordatorios_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error al cargar recordatorios: {e}")
                return []
        return []

    def cargar_recordatorios_pendientes(self) -> None:
        """Reschedule reminders that are still in the future.

        This method is called at startup to recover reminders from disk and
        restore pending Kivy timers.

        Args:
            None.

        Returns:
            None.

        Raises:
            ValueError: If one reminder has an invalid timestamp format in the
                persisted JSON file.
        """
        recordatorios = self.cargar_recordatorios()
        ahora = datetime.now()

        for recordatorio in recordatorios:
            hora_recordatorio = datetime.strptime(recordatorio["hora"], "%Y-%m-%d %H:%M:%S")
            if hora_recordatorio > ahora:
                segundos_restantes = (hora_recordatorio - ahora).total_seconds()
                Clock.schedule_once(lambda dt: self.mostrar_recordatorio(recordatorio["mensaje"]), segundos_restantes)
            else:
                self.eliminar_recordatorio(recordatorio["mensaje"])

    def eliminar_recordatorio(self, mensaje: str) -> None:
        """Delete reminder entries that match a given message.

        Args:
            mensaje (str): Reminder message used as delete key.

        Returns:
            None.

        Raises:
            No exception is propagated. File and JSON errors are logged.

        Examples:
            >>> mgr.eliminar_recordatorio("Tomar medicación")
        """
        recordatorios = self.cargar_recordatorios()
        recordatorios = [r for r in recordatorios if r["mensaje"] != mensaje]

        try:
            with open(self.recordatorios_file, "w", encoding="utf-8") as f:
                json.dump(recordatorios, f, ensure_ascii=False, indent=4)
            print(f"Recordatorio eliminado: {mensaje}")
        except Exception as e:
            print(f"Error al eliminar recordatorio: {e}")
