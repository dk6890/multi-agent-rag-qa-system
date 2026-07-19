from pathlib import Path

from cleaning import clean_text
from document_loader import load_document
from embedding import EmbeddingProvider
from schemas import Reference
from splitter import split_text
from vector_store import ChromaVectorStore


class RagService:
    def __init__(self) -> None:
        self._embedding_provider: EmbeddingProvider | None = None
        self._vector_store: ChromaVectorStore | None = None

    @property
    def embedding_provider(self) -> EmbeddingProvider:
        if self._embedding_provider is None:
            self._embedding_provider = EmbeddingProvider()
        return self._embedding_provider

    @property
    def vector_store(self) -> ChromaVectorStore:
        if self._vector_store is None:
            self._vector_store = ChromaVectorStore()
        return self._vector_store

    def index_file(self, *, file_id: int, file_path: str, file_name: str) -> int:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"file not found: {file_path}")

        pages = load_document(file_path)
        chunks = []
        for page in pages:
            cleaned = clean_text(page["text"])
            if not cleaned:
                continue
            for text in split_text(cleaned):
                chunks.append(
                    {
                        "chunkIndex": len(chunks) + 1,
                        "text": text,
                        "metadata": page.get("metadata") or {},
                    }
                )

        if not chunks:
            raise ValueError("no valid text content found in document")

        embeddings = self.embedding_provider.embed([chunk["text"] for chunk in chunks])
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

        keyword_references = self.vector_store.keyword_search(query=cleaned_question, top_k=top_k)
        query_embedding = self.embedding_provider.embed([cleaned_question])[0]
        vector_references = self.vector_store.search(query_embedding=query_embedding, top_k=top_k)
        raw_references = _merge_references(keyword_references, vector_references, top_k)
        return [Reference(**reference) for reference in raw_references]


def _merge_references(
    keyword_references: list[dict],
    vector_references: list[dict],
    top_k: int,
) -> list[dict]:
    merged = []
    seen = set()
    for reference in [*keyword_references, *vector_references]:
        key = reference.get("chunkId") or (
            reference.get("fileId"),
            reference.get("chunkText"),
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(reference)
        if len(merged) >= top_k:
            break
    return merged
