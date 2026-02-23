from transformers import AutoModel, AutoTokenizer
import os

# Dossier où ton application cherche le modèle
MODEL_DIR = "virtual_assistant/roberta_model"

# Crée le dossier s'il n'existe pas
os.makedirs(MODEL_DIR, exist_ok=True)

# Modèle à télécharger depuis HuggingFace (ici Roberta-base)
MODEL_NAME = "roberta-base"

print(f"🔹 Téléchargement du modèle {MODEL_NAME}...")

# Télécharge le modèle et le tokenizer
model = AutoModel.from_pretrained(MODEL_NAME)
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

# Sauvegarde localement dans le dossier attendu par ton app
model.save_pretrained(MODEL_DIR)
tokenizer.save_pretrained(MODEL_DIR)

print(f"✅ Modèle et tokenizer sauvegardés dans {MODEL_DIR}")
