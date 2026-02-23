import cv2  # Para captura de cámara y procesamiento de imágenes
import numpy as np  # Para operaciones numéricas y manejo de embeddings
import os
import json
import time
import tkinter as tk
from tkinter import messagebox, simpledialog
import onnxruntime as ort  # Para ejecutar el modelo ArcFace en formato ONNX
from sklearn.metrics.pairwise import cosine_similarity  # Para medir similitud entre vectores de embedding
from datetime import datetime  # Para registrar logs de acceso

FACE_DATA_PATH = "face_authentication/face_data.json"  # Ruta del archivo donde se almacenan los embeddings faciales
LOG_PATH = "logs/face_unlock_results.txt"  # Ruta del archivo de logs

# Cargar modelo ArcFace ONNX (resnet100)
MODEL_PATH = "face_authentication/arcface.onnx"
session = ort.InferenceSession(MODEL_PATH)  # Inicializa la sesión del modelo ONNX
input_name = session.get_inputs()[0].name  # Obtiene el nombre de la entrada del modelo

# Función auxiliar para mostrar alertas
def mostrar_alerta(titulo, mensaje):
    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo(titulo, mensaje)
    root.destroy()

# Función que registra un intento de acceso con fecha y resultado
def log_event(nombre, resultado, valor):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} - Usuario: {nombre} - Resultado: {resultado} - Similaridad: {valor:.4f}\n")

# Alinea la cara detectada centrando y recortando la región del rostro
def alinear_rostro(frame, bbox):
    x, y, w, h = bbox
    cx, cy = x + w // 2, y + h // 2
    size = max(w, h)
    x1 = max(cx - size // 2, 0)
    y1 = max(cy - size // 2, 0)
    x2 = x1 + size
    y2 = y1 + size
    face_img = frame[y1:y2, x1:x2]  # Extrae la región cuadrada alrededor del rostro
    return face_img

# Genera la embedding del rostro usando ArcFace y la normaliza con L2
def get_embedding(face_img):
    img = cv2.resize(face_img, (112, 112))  # Redimensiona a 112x112
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)  # Convierte a RGB
    img = img.astype(np.float32)  # Convierte a float32
    img = (img - 127.5) / 128.0  # Normalización típica para ArcFace
    img = np.transpose(img, (2, 0, 1))  # Canal primero
    img = np.expand_dims(img, axis=0)  # Añade dimensión batch
    embedding = session.run(None, {input_name: img})[0][0]  # Ejecuta el modelo y obtiene la embedding
    norm = np.linalg.norm(embedding)  # Normalización L2
    return embedding / norm if norm != 0 else embedding  # Devuelve embedding normalizada

# Carga los datos faciales del archivo JSON
face_data = {}
if os.path.exists(FACE_DATA_PATH):
    try:
        with open(FACE_DATA_PATH, "r") as f:
            content = f.read().strip()
            if content:
                face_data = json.loads(content)
    except json.JSONDecodeError:
        mostrar_alerta("Error", "Error al leer el archivo JSON de datos faciales.")
        face_data = {}

# Guarda múltiples embeddings del usuario registrado
def save_face(name, embeddings):
    face_data.clear()  # Solo se permite un usuario
    face_data[name] = embeddings  # Guarda la lista de embeddings
    with open(FACE_DATA_PATH, "w") as f:
        json.dump(face_data, f)
    mostrar_alerta("Registro completo", f"Usuario '{name}' registrado exitosamente.")

# Funciones auxiliares
def is_user_registered():
    return len(face_data) == 1

def get_registered_name():
    return list(face_data.keys())[0] if is_user_registered() else None

def simple_input(titulo, mensaje):
    root = tk.Tk()
    root.withdraw()
    valor = tk.simpledialog.askstring(titulo, mensaje)
    root.destroy()
    return valor

# Captura 5 imágenes del rostro y obtiene 5 embeddings alineadas y normalizadas
def capturar_embeddings():
    cap = cv2.VideoCapture(0)  # Inicia la cámara
    mostrar_alerta("Cámara", "Abriendo cámara. Colócate frente a ella...")
    embeddings = []
    while len(embeddings) < 5:  # Captura hasta tener 5 embeddings
        ret, frame = cap.read()
        if not ret:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)  # Convierte a escala de grises
        detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')  # Detector Haar
        faces = detector.detectMultiScale(gray, 1.3, 5)  # Detección de rostro
        for (x, y, w, h) in faces:
            rostro_alineado = alinear_rostro(frame, (x, y, w, h))  # Alinea el rostro detectado
            embedding = get_embedding(rostro_alineado)  # Genera embedding con ArcFace
            embeddings.append(embedding.tolist())  # Añade la embedding a la lista
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)  # Dibuja recuadro en pantalla
            break
        cv2.putText(frame, f"Captura {len(embeddings)}/5", (30, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.imshow("Registro facial", frame)
        cv2.waitKey(1)
    cap.release()
    cv2.destroyAllWindows()
    return embeddings  # Devuelve lista de 5 embeddings

# Flujo de registro de usuario
def register_new_user():
    name = get_registered_name()
    if name:
        mostrar_alerta("Error", f"Ya hay un usuario registrado: {name}")
        return None
    nombre_usuario = simple_input("Registro", "Introduce tu nombre:")
    if not nombre_usuario:
        return None
    embeddings = capturar_embeddings()  # Captura múltiples embeddings del rostro
    if embeddings:
        save_face(nombre_usuario, embeddings)  # Guarda las embeddings
        return nombre_usuario
    return None

# Compara una embedding actual con una lista de embeddings guardadas y calcula estadísticas
def reconocer_por_similitud(embedding_actual, embeddings_guardadas, threshold=0.5):
    similitudes = [cosine_similarity([embedding_actual], [e])[0][0] for e in embeddings_guardadas]  # Similaridades con cada vector
    max_sim = max(similitudes)  # Similaridad máxima
    prom_sim = np.mean(similitudes)  # Media
    std_sim = np.std(similitudes)  # Desviación estándar
    return max_sim, prom_sim, std_sim, max_sim > threshold  # Devuelve estadísticas y resultado booleano

# Verificación del usuario en tiempo real con logging y validación por similitud
def recognize_user():
    if not is_user_registered():
        return None
    known_name = get_registered_name()
    known_embeddings = face_data[known_name]  # Embeddings registrados
    cap = cv2.VideoCapture(0)  # Activa la cámara
    
    result = None
    valor_sim = 0
    start_time = time.time()
    while time.time() - start_time < 5:  # Tiempo límite de verificación
        ret, frame = cap.read()
        if not ret:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        faces = detector.detectMultiScale(gray, 1.3, 5)
        for (x, y, w, h) in faces:
            rostro_alineado = alinear_rostro(frame, (x, y, w, h))  # Alinea el rostro actual
            embedding_actual = get_embedding(rostro_alineado)  # Genera embedding actual
            max_sim, prom_sim, std_sim, valido = reconocer_por_similitud(embedding_actual, known_embeddings)  # Compara con embeddings guardadas
            valor_sim = max_sim
            if valido:
                result = known_name  # Si pasa el umbral, autenticación válida
                break
        cv2.imshow("Verificación facial", frame)
        cv2.waitKey(1)
    cap.release()
    cv2.destroyAllWindows()
    log_event(known_name, "ÉXITO" if result else "FALLO", valor_sim)  # Registro en el log
    return result  # Devuelve el nombre si fue reconocido
