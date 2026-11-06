from pathlib import Path
from threading import RLock

from cleaning import clean_text
from config import settings
from document_loader import load_document
from embedding import EmbeddingProvider, EmbeddingUnavailableError
from schemas import Reference
from splitter import split_document
from vector_store import ChromaVectorStore


class RagService:
    def __init__(self) -> None:
        self._embedding_provider: EmbeddingProvider | None = None
        self._vector_store: ChromaVectorStore | None = None
        self._lexical_store: ChromaVectorStore | None = None
        self._embedding_error: str | None = None
        self._embedding_lock = RLock()
        self.last_search_warning: str | None = None

    @property
    def embedding_provider(self) -> EmbeddingProvider:
        with self._embedding_lock:
            if self._embedding_error:
                raise EmbeddingUnavailableError(self._embedding_error)
            if self._embedding_provider is None:
                try:
                    self._embedding_provider = EmbeddingProvider()
                except EmbeddingUnavailableError as exc:
                    self._embedding_error = str(exc)
                    raise
        return self._embedding_provider

    @property
    def vector_store(self) -> ChromaVectorStore:
        with self._embedding_lock:
            if self._vector_store is None:
                self._vector_store = ChromaVectorStore(self.embedding_provider.model_fingerprint)
        return self._vector_store

    def health_status(self, *, load_embedding: bool = False) -> dict:
        if load_embedding:
            try:
                self.embedding_provider
            except EmbeddingUnavailableError:
                pass
        provider = self._embedding_provider
        status = "ready" if provider else "unavailable" if self._embedding_error else "not_loaded"
        result = {"embedding": {
            "status": status, "provider": provider.provider_name if provider else None,
            "model": settings.embedding_model_name, "error": self._embedding_error,
        }}
        if provider:
            result["embedding"].update({"dimension": provider.dimension,
                                        "maxInputTokens": provider.max_input_tokens,
                                        "fingerprint": provider.model_fingerprint})
            result["index"] = self.vector_store.diagnostics()
        return result

    def index_file(self, *, file_id: int, file_path: str, file_name: str) -> int:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"file not found: {file_path}")

        pages = load_document(file_path)
        provider = self.embedding_provider
        chunks = split_document(pages, token_counter=provider.count_tokens,
                                max_tokens=provider.max_input_tokens, file_name=file_name)

        if not chunks:
            raise ValueError("no valid text content found in document")

        embeddings = provider.embed([chunk["text"] for chunk in chunks])
        return self.vector_store.upsert_chunks(
            file_id=file_id,
            file_name=file_name,
            chunks=chunks,
            embeddings=embeddings,
        )

    def search(self, *, question: str, top_k: int) -> list[Reference]:
        cleaned_question = clean_text(question)
        if not cleaned_question:
            raise ValueError("question must not be blank")

        if not 1 <= top_k <= 50:
            raise ValueError("top_k must be between 1 and 50")
        candidates = min(200, max(20, top_k * settings.retrieval_candidate_multiplier))
        self.last_search_warning = None
        try:
            provider = self.embedding_provider
        except EmbeddingUnavailableError:
            self.last_search_warning = "Embedding unavailable; returning BM25 lexical results only. Prepare the local model and restart."
            if self._lexical_store is None:
                self._lexical_store = ChromaVectorStore()
            references = self._lexical_store.keyword_search(query=cleaned_question, top_k=top_k)
            for reference in references:
                reference["metadata"].update({"searchMode": "lexical-only", "degraded": True})
            return [Reference(**reference) for reference in references]

        keyword_references = self.vector_store.keyword_search(query=cleaned_question, top_k=candidates)
        query_embedding = provider.embed_query(cleaned_question)
        vector_references = self.vector_store.search(query_embedding=query_embedding, top_k=candidates)
        raw_references = _merge_references(keyword_references, vector_references, top_k)
        if any(reference["metadata"].get("legacyIndex") for reference in raw_references):
            self.last_search_warning = "Some files still use the legacy lexical index. Reindex them to enable semantic retrieval."
        return [Reference(**reference) for reference in raw_references]


def _merge_references(
    keyword_references: list[dict],
    vector_references: list[dict],
    top_k: int,
) -> list[dict]:
    merged = {}
    k = settings.retrieval_rrf_k
    for route, references in (("bm25", keyword_references), ("vector", vector_references)):
        seen = set()
        for rank, reference in enumerate(references, start=1):
            key = reference.get("chunkId") or (reference.get("fileId"), reference.get("chunkText"))
            if key in seen:
                continue
            seen.add(key)
            if key not in merged:
                merged[key] = {**reference, "score": 0.0, "metadata": {**(reference.get("metadata") or {})}}
            result = merged[key]
            result["score"] += 1 / (k + rank)
            result["metadata"][f"{route}Rank"] = rank
            result["metadata"].update(reference.get("metadata") or {})
    ranked = sorted(merged.values(), key=lambda reference: reference["score"], reverse=True)[:top_k]
    for reference in ranked:
        metadata = reference["metadata"]
        metadata["fusionScore"] = reference["score"]
        metadata["retriever"] = "rrf"
        metadata["searchMode"] = ("hybrid" if "bm25Rank" in metadata and "vectorRank" in metadata
                                  else "vector-only" if "vectorRank" in metadata else "lexical-only")
        # A normalized rank-fusion score, not a probability or cosine similarity.
        reference["score"] = reference["score"] / (2 / (k + 1))
    return ranked
