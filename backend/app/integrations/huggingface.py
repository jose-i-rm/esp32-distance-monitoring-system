"""Cliente base para la futura clasificación de imágenes con Hugging Face.

Este módulo NO está conectado a ninguna ruta todavía. Sirve como contrato para la fase de
visión artificial descrita en docs/futuras-integraciones.md.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Classification:
    label: str
    score: float


class HuggingFaceClassifier:
    """Envoltura mínima sobre la Inference API de Hugging Face.

    Variables de entorno previstas:
        HF_API_TOKEN  -> token de acceso (pendiente de crear).
        HF_MODEL_ID   -> p. ej. "google/vit-base-patch16-224".
    """

    def __init__(self, api_token: str, model_id: str) -> None:
        self.api_token = api_token
        self.model_id = model_id

    def classify(self, image_bytes: bytes) -> list[Classification]:
        raise NotImplementedError("Integración con Hugging Face planificada para la fase 4 del roadmap.")
