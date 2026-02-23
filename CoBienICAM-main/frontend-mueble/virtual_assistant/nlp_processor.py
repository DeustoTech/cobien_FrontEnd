import joblib
from transformers import AutoTokenizer, AutoModel
import torch

class IntentClassifier:
    def __init__(self):
        # Cargar el modelo y el tokenizador correctamente (RoBERTa)
        self.clf = joblib.load("virtual_assistant/intent_classifier_roberta.joblib")
        self.label_encoder = joblib.load("virtual_assistant/label_encoder_roberta.joblib")
        self.tokenizer = AutoTokenizer.from_pretrained("virtual_assistant/roberta_tokenizer")
        self.model = AutoModel.from_pretrained("virtual_assistant/roberta_model")

    def predecir_intencion(self, texto):
        texto = texto.lower().strip()
        inputs = self.tokenizer(texto, return_tensors="pt", truncation=True, padding=True)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            embedding = outputs.last_hidden_state.mean(dim=1).squeeze().numpy()
        
        # Asegurarnos de que el embedding siempre sea 2D y tenga 768 dimensiones
        if len(embedding.shape) == 1:
            embedding = embedding.reshape(1, -1)  # Convertir a 2D si es 1D
        
        # Verificar que el vector tiene 768 dimensiones
        if embedding.shape[1] != 768:
            raise ValueError(f"El vector de embedding tiene {embedding.shape[1]} dimensiones, se esperaban 768.")

        prediccion = self.clf.predict(embedding)
        intencion = self.label_encoder.inverse_transform(prediccion)
        return intencion[0]
