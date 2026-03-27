from pathlib import Path

import joblib
import torch
from transformers import AutoModel, AutoTokenizer


BASE_DIR = Path(__file__).resolve().parent
TOKENIZER_DIR = BASE_DIR / "roberta_tokenizer"
MODEL_DIR = BASE_DIR / "roberta_model"
CLASSIFIER_PATH = BASE_DIR / "intent_classifier_roberta.joblib"
LABEL_ENCODER_PATH = BASE_DIR / "label_encoder_roberta.joblib"
MODEL_WEIGHT_FILES = (
    "model.safetensors",
    "pytorch_model.bin",
    "tf_model.h5",
    "model.ckpt.index",
    "flax_model.msgpack",
)


def _has_local_model_weights() -> bool:
    return any((MODEL_DIR / filename).exists() for filename in MODEL_WEIGHT_FILES)


class IntentClassifier:
    def __init__(self):
        self.clf = joblib.load(CLASSIFIER_PATH)
        self.label_encoder = joblib.load(LABEL_ENCODER_PATH)
        self.tokenizer = AutoTokenizer.from_pretrained(str(TOKENIZER_DIR))
        if _has_local_model_weights():
            self.model = AutoModel.from_pretrained(str(MODEL_DIR))
        else:
            self.model = AutoModel.from_pretrained("roberta-base")

    def predecir_intencion(self, texto):
        texto = texto.lower().strip()
        inputs = self.tokenizer(texto, return_tensors="pt", truncation=True, padding=True)

        with torch.no_grad():
            outputs = self.model(**inputs)
            embedding = outputs.last_hidden_state.mean(dim=1).squeeze().numpy()

        if len(embedding.shape) == 1:
            embedding = embedding.reshape(1, -1)

        if embedding.shape[1] != 768:
            raise ValueError(
                f"Embedding vector has {embedding.shape[1]} dimensions; expected 768."
            )

        prediccion = self.clf.predict(embedding)
        intencion = self.label_encoder.inverse_transform(prediccion)
        return intencion[0]
