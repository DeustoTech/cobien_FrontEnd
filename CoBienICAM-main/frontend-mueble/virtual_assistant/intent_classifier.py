import json
import joblib
import torch
from transformers import AutoTokenizer, AutoModel
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder
import numpy as np
import warnings

# Suprimir las advertencias de HuggingFace
warnings.filterwarnings("ignore")

# 1. Cargar dataset
with open("virtual_assistant/intent_dataset.json", "r", encoding="utf-8") as f:
    data = json.load(f)

texts = [d["text"].lower().strip() for d in data]
intents = [d["intent"] for d in data]

# 2. Cargar modelo RoBERTa y tokenizer (sin la capa "pooler")
tokenizer = AutoTokenizer.from_pretrained("roberta-base")
model = AutoModel.from_pretrained("roberta-base", add_pooling_layer=False)

# 3. Generar embeddings de RoBERTa (en 2D)
def embed_texts(texts):
    embeddings = []
    with torch.no_grad():
        for text in texts:
            inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True)
            outputs = model(**inputs)
            # Usamos la última capa para los embeddings (sin pooler)
            embedding = outputs.last_hidden_state.mean(dim=1).squeeze().numpy()
            embeddings.append(embedding)
    
    return np.vstack(embeddings)  # Usar np.vstack para garantizar 2D

X = embed_texts(texts)
X = X.reshape(len(texts), -1)  # Aseguramos que sea 2D

# 4. Convertir las etiquetas a valores numéricos
label_encoder = LabelEncoder()
y = label_encoder.fit_transform(intents)

# 5. Entrenar clasificador (Logistic Regression)
clf = LogisticRegression(max_iter=1000)
clf.fit(X, y)

# 6. Guardar modelo, encoder y RoBERTa
joblib.dump(clf, "virtual_assistant/intent_classifier_roberta.joblib")
joblib.dump(label_encoder, "virtual_assistant/label_encoder_roberta.joblib")
tokenizer.save_pretrained("virtual_assistant/roberta_tokenizer")
model.save_pretrained("virtual_assistant/roberta_model")

print("Clasificador basado en RoBERTa entrenado y guardado.")
