import hashlib
import json
import logging
from pathlib import Path

from config import settings


class EmbeddingUnavailableError(RuntimeError):
    """A real embedding model is required to create a semantic index."""


class EmbeddingProvider:
    def __init__(self) -> None:
        self.provider_name = "sentence-transformers"
        self.last_error: str | None = None
        local_path = Path(settings.embedding_local_path) if settings.embedding_local_path else None
        source = str(local_path) if local_path and (local_path / "modules.json").is_file() else settings.embedding_model_name
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                source, device="cpu",
                local_files_only=not settings.embedding_allow_download,
                trust_remote_code=False,
            )
            self.tokenizer = self._model.tokenizer
            self.max_input_tokens = min(int(self._model.max_seq_length), settings.chunk_max_tokens)
            if self.max_input_tokens <= self.count_tokens(""):
                raise ValueError("chunk_max_tokens is too small for the model tokenizer")
            self.model_fingerprint = self._fingerprint(local_path)
        except Exception as exc:
            logging.exception("Could not initialize the semantic embedding model")
            raise EmbeddingUnavailableError(
                "Semantic embedding unavailable. Install compatible dependencies and prepare "
                "the local sentence-transformers model with scripts/prepare-rag.ps1; "
                f"no hash vectors were generated. Cause: {type(exc).__name__}"
            ) from exc

    @property
    def dimension(self) -> int:
        getter = getattr(self._model, "get_embedding_dimension", None)
        return int(getter() if getter else self._model.get_sentence_embedding_dimension())

    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text, add_special_tokens=True, truncation=False))

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if any(self.count_tokens(text) > self.max_input_tokens for text in texts):
            raise ValueError("Embedding input exceeds the model token budget; split the document first")
        vectors = self._model.encode(
            texts, batch_size=settings.embedding_batch_size,
            normalize_embeddings=True, show_progress_bar=False,
        )
        return [vector.tolist() for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        tokens = self.tokenizer.encode(text, add_special_tokens=False, truncation=False)
        budget = self.max_input_tokens - self.tokenizer.num_special_tokens_to_add(pair=False)
        if len(tokens) > budget:
            text = self.tokenizer.decode(tokens[:budget], skip_special_tokens=True)
        return self.embed([text])[0]

    def _fingerprint(self, local_path: Path | None) -> str:
        digest = hashlib.sha256()
        digest.update(json.dumps({
            "model": settings.embedding_model_name,
            "dimension": self.dimension,
            "maxTokens": self.max_input_tokens,
            "normalized": True,
        }, sort_keys=True).encode("utf-8"))
        if local_path and local_path.is_dir():
            # Identify checkpoint contents, not only a model name or vector dimension.
            for path in sorted(local_path.rglob("*")):
                if not path.is_file() or ".cache" in path.parts:
                    continue
                if path.suffix not in {".json", ".safetensors", ".bin", ".model", ".txt"}:
                    continue
                digest.update(path.relative_to(local_path).as_posix().encode("utf-8"))
                with path.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(block)
        else:
            config = self._model[0].auto_model.config
            digest.update(config.to_json_string().encode("utf-8"))
            digest.update(str(getattr(config, "_commit_hash", "")).encode("utf-8"))
        return digest.hexdigest()[:20]
