from face_authentication.face_unlock import (
    is_user_registered,
    register_new_user,
    recognize_user,
    get_registered_name
)
from datetime import datetime
import os
import sys
import tkinter as tk
from tkinter import messagebox

def mostrar_alerta(titulo, mensaje):
    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo(titulo, mensaje)
    root.destroy()

def log_event(name, tipo="acceso"):
    """Guarda un registro de accesos o registros en un archivo."""
    log_file = "logs/unlock_log.txt"
    timestamp = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    with open(log_file, "a", encoding="utf-8") as file:
        file.write(f"{timestamp}, {name}, {tipo}\n")

def mostrar_bienvenida():
    mensaje = "Bienvenido.\n Pulse ACEPTAR para comenzar el reconocimiento..."
    mostrar_alerta("Bienvenida", mensaje)

def authenticate_user():
    """Control de acceso con modo invitado."""
    if not is_user_registered():
        return None

    mostrar_bienvenida()
    name = recognize_user()

    if name:
        log_event(name, "acceso")
        return name
    else:
        log_event("Invitado", "acceso (no reconocido)")
        return "Invitado"
