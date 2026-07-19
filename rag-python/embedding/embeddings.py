import hashlib
import math

from config import settings


class EmbeddingProvider:
    def __init__(self) -> None:
        self._model = None
        self.provider_name = "hash"
        self.last_error: str | None = None
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(settings.embedding_model_name)
            self.provider_name = "sentence-transformers"
        except Exception as exc:
            self.last_error = (
                "sentence-transformers model unavailable; using deterministic "
                f"HashEmbedding fallback. reason: {exc}"
            )

    @property
    def dimension(self) -> int:
        if self._model is not None:
            return int(self._model.get_sentence_embedding_dimension())
        return settings.embedding_dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._model is not None:
            vectors = self._model.encode(texts, normalize_embeddings=True)
            return [vector.tolist() for vector in vectors]
        return [self._hash_embed(text) for text in texts]

    def _hash_embed(self, text: str) -> list[float]:
        vector = [0.0] * settings.embedding_dimension
        tokens = text.lower().split()
        if not tokens:
            tokens = [text.lower()]
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8", errors="ignore")).digest()
            for offset in range(0, len(digest), 4):
                bucket = int.from_bytes(digest[offset : offset + 2], "big") % settings.embedding_dimension
                sign = 1.0 if digest[offset + 2] % 2 == 0 else -1.0
                vector[bucket] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]
