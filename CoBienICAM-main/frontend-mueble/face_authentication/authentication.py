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

def reiniciar_programa():
    """Reinicia el script."""
    python = sys.executable
    os.execl(python, python, *sys.argv)

def mostrar_bienvenida():
    mensaje = "Bienvenido.\n Pulse aqui para comenzar."
    mostrar_alerta("Bienvenida", mensaje)

def authenticate_user():
    """Control principal de acceso."""
    if not is_user_registered():
        mostrar_alerta("Registro", "No hay usuario registrado. Iniciando registro...")
        name = register_new_user()
        if name:
            log_event(name, "registro")
            return name
        else:
            mostrar_alerta("Error", "Registro fallido. Reiniciando...")
            reiniciar_programa()
            return None

    mostrar_bienvenida()
    name = recognize_user()

    if name:
        log_event(name, "acceso")
        return name
    else:
        mostrar_alerta("Acceso denegado", "Usuario no reconocido. Reiniciando...")
        reiniciar_programa()
        return None
