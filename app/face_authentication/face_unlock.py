import cv2  # For camera capture and image processing
import numpy as np  # For numerical operations and handling embeddings
import os
import json
import time
import tkinter as tk
from tkinter import messagebox, simpledialog
import onnxruntime as ort  # To run the ArcFace model in ONNX format
from sklearn.metrics.pairwise import cosine_similarity  # To measure similarity between embedding vectors
from datetime import datetime  # To log access attempts

FACE_DATA_PATH = "face_authentication/face_data.json"  # Path to the file where facial embeddings are stored
LOG_PATH = "logs/face_unlock_results.txt"  # Path to the log file

# Load ArcFace ONNX model (resnet100)
MODEL_PATH = "face_authentication/arcface.onnx"
session = ort.InferenceSession(MODEL_PATH)  # Initialize the ONNX model session
input_name = session.get_inputs()[0].name  # Get the model input name

# Helper function to show alerts
def mostrar_alerta(titulo, mensaje):
    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo(titulo, mensaje)
    root.destroy()

# Function that logs an access attempt with timestamp and result
def log_event(nombre, resultado, valor):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} - Usuario: {nombre} - Resultado: {resultado} - Similaridad: {valor:.4f}\n")

# Align the detected face by centering and cropping the face region
def alinear_rostro(frame, bbox):
    x, y, w, h = bbox
    cx, cy = x + w // 2, y + h // 2
    size = max(w, h)
    x1 = max(cx - size // 2, 0)
    y1 = max(cy - size // 2, 0)
    x2 = x1 + size
    y2 = y1 + size
    face_img = frame[y1:y2, x1:x2]  # Extract the square region around the face
    return face_img

# Generate face embedding using ArcFace and normalize with L2
def get_embedding(face_img):
    img = cv2.resize(face_img, (112, 112))  # Resize to 112x112
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)  # Convert to RGB
    img = img.astype(np.float32)  # Convert to float32
    img = (img - 127.5) / 128.0  # Typical normalization for ArcFace
    img = np.transpose(img, (2, 0, 1))  # Channel-first
    img = np.expand_dims(img, axis=0)  # Add batch dimension
    embedding = session.run(None, {input_name: img})[0][0]  # Run the model and get the embedding
    norm = np.linalg.norm(embedding)  # L2 normalization
    return embedding / norm if norm != 0 else embedding  # Return normalized embedding

# Load facial data from the JSON file
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

# Save multiple embeddings for the registered user
def save_face(name, embeddings):
    face_data.clear()  # Only one user is allowed
    face_data[name] = embeddings  # Save the list of embeddings
    with open(FACE_DATA_PATH, "w") as f:
        json.dump(face_data, f)
    mostrar_alerta("Registro completo", f"Usuario '{name}' registrado exitosamente.")

# Helper functions
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

# Capture 5 face images and obtain 5 aligned and normalized embeddings
def capturar_embeddings():
    cap = cv2.VideoCapture(0)  # Start the camera
    mostrar_alerta("Cámara", "Abriendo cámara. Colócate frente a ella...")
    embeddings = []
    while len(embeddings) < 5:  # Capture until we have 5 embeddings
        ret, frame = cap.read()
        if not ret:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)  # Convierte a escala de grises
        detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')  # Detector Haar
        faces = detector.detectMultiScale(gray, 1.3, 5)  # Detección de rostro
        for (x, y, w, h) in faces:
            rostro_alineado = alinear_rostro(frame, (x, y, w, h))  # Align the detected face
            embedding = get_embedding(rostro_alineado)  # Genera embedding con ArcFace
            embeddings.append(embedding.tolist())  # Añade la embedding a la lista
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)  # Draw rectangle on screen
            break
        cv2.putText(frame, f"Captura {len(embeddings)}/5", (30, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.imshow("Registro facial", frame)
        cv2.waitKey(1)
    cap.release()
    cv2.destroyAllWindows()
    return embeddings  # Return list of 5 embeddings

# User registration flow
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

# Compare a current embedding with a list of stored embeddings and compute statistics
def reconocer_por_similitud(embedding_actual, embeddings_guardadas, threshold=0.5):
    similitudes = [cosine_similarity([embedding_actual], [e])[0][0] for e in embeddings_guardadas]  # Similarities with each vector
    max_sim = max(similitudes)  # Maximum similarity
    prom_sim = np.mean(similitudes)  # Mean
    std_sim = np.std(similitudes)  # Standard deviation
    return max_sim, prom_sim, std_sim, max_sim > threshold  # Return stats and boolean result

# Real-time user verification with logging and similarity validation
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
            rostro_alineado = alinear_rostro(frame, (x, y, w, h))  # Align the current face
            embedding_actual = get_embedding(rostro_alineado)  # Generate current embedding
            max_sim, prom_sim, std_sim, valido = reconocer_por_similitud(embedding_actual, known_embeddings)  # Compara con embeddings guardadas
            valor_sim = max_sim
            if valido:
                result = known_name  # Si pasa el umbral, autenticación válida
                break
        cv2.imshow("Verificación facial", frame)
        cv2.waitKey(1)
    cap.release()
    cv2.destroyAllWindows()
    log_event(known_name, "SUCCESS" if result else "FAILURE", valor_sim)  # Log the result
    return result  # Return the name if recognized
