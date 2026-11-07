"""
Local, zero-cost embedding service using Sentence Transformers.
Uses sentence-transformers/all-MiniLM-L6-v2 (384 dimensions).
Supports local CPU execution and optional CUDA acceleration with graceful fallback.
"""

import logging
import threading
from typing import List, Optional

from backend.app.config import settings
from backend.app.vectorstore.interfaces import BaseEmbeddingService

logger = logging.getLogger(__name__)


class LocalSentenceTransformerService(BaseEmbeddingService):
    """
    Thread-safe, lazy-initialized embedding service powered by local SentenceTransformers.
    """

    def __init__(self, model_name: Optional[str] = None) -> None:
        self.model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self._model = None
        self._device: str = "cpu"
        self._lock = threading.Lock()
        self._dimension = 384  # all-MiniLM-L6-v2 standard dimension

    def _determine_device(self) -> str:
        """Determines best available device: CUDA GPU or CPU."""
        try:
            import torch
            if torch.cuda.is_available():
                device_name = torch.cuda.get_device_name(0)
                logger.info(f"CUDA GPU detected: {device_name}. Utilizing GPU for embeddings.")
                return "cuda"
        except Exception as e:
            logger.debug(f"CUDA probe exception: {e}. Falling back to CPU.")
        logger.info("Using local CPU execution for embeddings.")
        return "cpu"

    def _load_model(self) -> None:
        """Loads SentenceTransformer model with graceful GPU->CPU fallback."""
        if self._model is not None:
            return

        with self._lock:
            if self._model is not None:
                return

            from sentence_transformers import SentenceTransformer

            target_device = self._determine_device()
            logger.info(f"Loading embedding model '{self.model_name}' on device '{target_device}'...")

            try:
                self._model = SentenceTransformer(self.model_name, device=target_device)
                self._device = target_device
                logger.info(f"Embedding model '{self.model_name}' successfully loaded on {self._device}.")
            except Exception as e:
                if target_device != "cpu":
                    logger.warning(f"Failed to load embedding model on {target_device}: {e}. Retrying on CPU.")
                    self._model = SentenceTransformer(self.model_name, device="cpu")
                    self._device = "cpu"
                    logger.info("Embedding model loaded on fallback CPU.")
                else:
                    logger.error(f"Fatal error loading embedding model on CPU: {e}")
                    raise

    @property
    def model(self):
        if self._model is None:
            self._load_model()
        return self._model

    def embed_text(self, text: str) -> List[float]:
        """Generate a dense embedding vector for a single text query or snippet."""
        clean_text = text.strip() if text else " "
        embedding = self.model.encode(clean_text, convert_to_numpy=True, normalize_embeddings=True)
        return embedding.tolist()

    def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """Generate dense embeddings for a batch of strings."""
        if not texts:
            return []

        cleaned = [t.strip() if t.strip() else " " for t in texts]
        embeddings = self.model.encode(
            cleaned,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embeddings.tolist()

    def dimension(self) -> int:
        return self._dimension

    def get_device(self) -> str:
        if self._model is None:
            self._load_model()
        return self._device


# Global default embedding service instance
embedding_service = LocalSentenceTransformerService()

