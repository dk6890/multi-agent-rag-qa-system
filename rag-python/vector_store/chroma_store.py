import re
from pathlib import Path
from typing import Any

from config import settings


class ChromaVectorStore:
    def __init__(self) -> None:
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError("chromadb is required for vector storage") from exc

        store_path = Path(settings.vector_store_path)
        store_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(store_path))
        self._collection = self._client.get_or_create_collection(
            name=settings.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert_chunks(
        self,
        *,
        file_id: int,
        file_name: str,
        chunks: list[dict[str, Any]],
        embeddings: list[list[float]],
    ) -> int:
        ids = []
        documents = []
        metadatas = []

        for chunk in chunks:
            chunk_index = chunk["chunkIndex"]
            chunk_id = f"{file_id}-{chunk_index:04d}"
            metadata = {
                "fileId": file_id,
                "fileName": file_name,
                "chunkId": chunk_id,
                **_flatten_metadata(chunk.get("metadata") or {}),
            }
            ids.append(chunk_id)
            documents.append(chunk["text"])
            metadatas.append(metadata)

        if not ids:
            return 0

        self._collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        return len(ids)

    def search(self, *, query_embedding: list[float], top_k: int) -> list[dict[str, Any]]:
        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        references = []
        for document, metadata, distance in zip(documents, metadatas, distances):
            score = max(0.0, 1.0 - float(distance))
            if score <= 0.1:
                continue
            references.append(
                {
                    "fileId": int(metadata.get("fileId", 0)),
                    "fileName": str(metadata.get("fileName", "")),
                    "chunkText": document,
                    "score": score,
                    "chunkId": metadata.get("chunkId"),
                    "metadata": _public_metadata(metadata),
                }
            )
        return references

    def keyword_search(self, *, query: str, top_k: int) -> list[dict[str, Any]]:
        tokens = _tokenize_query(query)
        if not tokens:
            return []

        result = self._collection.get(include=["documents", "metadatas"])
        documents = result.get("documents", [])
        metadatas = result.get("metadatas", [])

        scored = []
        for document, metadata in zip(documents, metadatas):
            text = document or ""
            lowered = text.lower()
            hit_count = sum(lowered.count(token) for token in tokens)
            if hit_count <= 0:
                continue
            score = min(0.95, 0.55 + hit_count * 0.08)
            scored.append(
                (
                    score,
                    {
                        "fileId": int(metadata.get("fileId", 0)),
                        "fileName": str(metadata.get("fileName", "")),
                        "chunkText": text,
                        "score": score,
                        "chunkId": metadata.get("chunkId"),
                        "metadata": _public_metadata(metadata),
                    },
                )
            )

        scored.sort(key=lambda item: item[0], reverse=True)
        return [reference for _, reference in scored[:top_k]]


def _flatten_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    flat = {}
    for key, value in metadata.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            flat[key] = value
        else:
            flat[key] = str(value)
    return flat


def _public_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in metadata.items()
        if key not in {"fileId", "fileName", "chunkId"}
    }


def _tokenize_query(query: str) -> list[str]:
    lowered = query.lower().strip()
    tokens = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]{2,}", lowered)
    if not tokens and len(lowered) >= 2:
        tokens = [lowered]
    return list(dict.fromkeys(tokens))
