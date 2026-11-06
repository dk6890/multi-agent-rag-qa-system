import json
import logging
import re
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

import jieba
from rank_bm25 import BM25Plus

from config import settings


logger = logging.getLogger(__name__)
jieba.setLogLevel(logging.WARNING)
STOP_WORDS = {"\u7684", "\u4e86", "\u6211", "\u4f60", "\u60f3", "\u4e00\u4e0b", "\u8bf7", "\u8bf7\u95ee", "\u4ec0\u4e48", "\u600e\u4e48", "\u8fd9\u4e2a", "\u4e00\u4e2a", "\u80fd", "\u5417", "\u5462", "\u662f", "\u6709"}


class ChromaVectorStore:
    def __init__(self, model_fingerprint: str | None = None) -> None:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        self.model_fingerprint = model_fingerprint
        self._path = Path(settings.vector_store_path)
        self._path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(self._path), settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._lock = RLock()
        self._cache_key = None
        self._bm25 = None
        self._records = []
        self._corpus = []
        self.collection_name = f"{settings.collection_name}_v2_{model_fingerprint}" if model_fingerprint else settings.collection_name
        if model_fingerprint:
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name, metadata={
                    "hnsw:space": "cosine", "modelFingerprint": model_fingerprint,
                    "fileGenerations": "{}", "indexVersion": 2,
                },
            )
            if (self._collection.metadata or {}).get("modelFingerprint") != model_fingerprint:
                raise ValueError("Embedding fingerprint mismatch; create a separate semantic index")
        else:
            self._collection = self._existing(settings.collection_name)

    def _existing(self, name: str):
        from chromadb.errors import NotFoundError

        try:
            return self._client.get_collection(name=name)
        except NotFoundError:
            return None

    def _generations(self) -> dict[str, str]:
        if not self.model_fingerprint:
            return {}
        self._collection = self._client.get_collection(self.collection_name)
        return json.loads((self._collection.metadata or {}).get("fileGenerations", "{}"))

    def _active_where(self, generations: dict[str, str]) -> dict:
        return {"generation": {"$in": list(generations.values())}}

    def upsert_chunks(self, *, file_id: int, file_name: str,
                      chunks: list[dict[str, Any]], embeddings: list[list[float]]) -> int:
        if not self.model_fingerprint:
            raise ValueError("A real embedding fingerprint is required for indexing")
        if not chunks or len(chunks) != len(embeddings):
            raise ValueError("Chunks and embeddings must be non-empty and aligned")
        generation = uuid4().hex
        ids = [f"{file_id}-{generation}-{chunk['chunkIndex']:04d}" for chunk in chunks]
        metadatas = [{
            **_flatten_metadata(chunk.get("metadata") or {}),
            "fileId": file_id, "fileName": file_name, "chunkId": chunk_id,
            "chunkIndex": chunk["chunkIndex"], "generation": generation,
            "modelFingerprint": self.model_fingerprint, "indexVersion": 2,
        } for chunk_id, chunk in zip(ids, chunks)]
        with self._lock:
            generations = self._generations()
            try:
                batch_size = min(256, self._client.get_max_batch_size())
                for start in range(0, len(ids), batch_size):
                    end = start + batch_size
                    self._collection.upsert(
                        ids=ids[start:end], documents=[chunk["text"] for chunk in chunks[start:end]],
                        embeddings=embeddings[start:end], metadatas=metadatas[start:end],
                    )
                # One persisted metadata update publishes the fully written generation.
                generations[str(file_id)] = generation
                self._collection.modify(metadata={
                    **{key: value for key, value in self._collection.metadata.items() if not key.startswith("hnsw:")},
                    "fileGenerations": json.dumps(generations, sort_keys=True),
                })
            except Exception:
                try:
                    self._collection.delete(where={"generation": generation})
                except Exception:
                    logger.exception("Could not remove an unpublished indexing generation")
                raise
            self._cache_key = None
            try:
                self._collection.delete(where={"$and": [
                    {"fileId": file_id}, {"generation": {"$ne": generation}},
                ]})
            except Exception:
                # The new generation is committed; obsolete records remain invisible.
                logger.exception("Could not clean up an obsolete indexing generation")
        return len(chunks)

    def search(self, *, query_embedding: list[float], top_k: int) -> list[dict[str, Any]]:
        if not self.model_fingerprint:
            raise ValueError("Legacy vectors may only be used for lexical retrieval")
        with self._lock:
            generations = self._generations()
            if not generations:
                return []
            where = self._active_where(generations)
            count = len(self._collection.get(where=where, include=[])['ids'])
            if not count or top_k < 1:
                return []
            result = self._collection.query(
                query_embeddings=[query_embedding], n_results=min(top_k, count), where=where,
                include=["documents", "metadatas", "distances"],
            )
        references = []
        for text, metadata, distance in zip(result["documents"][0], result["metadatas"][0], result["distances"][0]):
            score = max(0.0, min(1.0, 1.0 - float(distance)))
            if score >= settings.vector_similarity_threshold:
                references.append(_reference(text, metadata, score, retriever="vector", vectorScore=score))
        return references

    def _snapshot(self) -> None:
        generations = self._generations()
        legacy = self._existing(settings.collection_name)
        key = (json.dumps(generations, sort_keys=True), legacy.count() if legacy is not None else 0,
               tuple((p.name, p.stat().st_mtime_ns) for p in self._path.glob("chroma.sqlite3*")))
        if self._cache_key == key:
            return
        records = []
        if self.model_fingerprint and generations:
            result = self._collection.get(where=self._active_where(generations), include=["documents", "metadatas"])
            records.extend(zip(result["documents"], result["metadatas"]))
        if legacy is not None:
            result = legacy.get(include=["documents", "metadatas"])
            records.extend((text, {**metadata, "legacyIndex": True})
                           for text, metadata in zip(result["documents"], result["metadatas"])
                           if str(metadata.get("fileId")) not in generations)
        self._records = [(text or "", metadata) for text, metadata in records]
        self._corpus = [_tokenize_query(text) for text, _ in self._records]
        self._bm25 = BM25Plus(self._corpus) if any(self._corpus) else None
        self._cache_key = key

    def keyword_search(self, *, query: str, top_k: int) -> list[dict[str, Any]]:
        tokens = _tokenize_query(query)
        if not tokens or top_k < 1:
            return []
        with self._lock:
            self._snapshot()
            if self._bm25 is None:
                return []
            scores = self._bm25.get_scores(tokens)
            query_terms = set(tokens)
            ranked = sorted((i for i, words in enumerate(self._corpus) if query_terms.intersection(words)),
                            key=lambda i: float(scores[i]), reverse=True)[:top_k]
            return [_reference(self._records[i][0], self._records[i][1], float(scores[i]) / (1 + float(scores[i])),
                               retriever="bm25", lexicalScore=float(scores[i])) for i in ranked]

    def diagnostics(self) -> dict:
        with self._lock:
            generations = self._generations()
            count = 0
            if self.model_fingerprint and generations:
                count = len(self._collection.get(where=self._active_where(generations), include=[])['ids'])
            legacy = self._existing(settings.collection_name)
            return {"collection": self.collection_name, "chunkCount": count,
                    "indexedFiles": len(generations), "legacyChunkCount": legacy.count() if legacy is not None else 0}


def _reference(text: str, metadata: dict, score: float, **diagnostics) -> dict:
    return {"fileId": int(metadata.get("fileId", 0)), "fileName": str(metadata.get("fileName", "")),
            "chunkText": text, "score": score, "chunkId": metadata.get("chunkId"),
            "metadata": {**_public_metadata(metadata), **diagnostics}}


def _flatten_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {key: value if isinstance(value, (str, int, float, bool)) else json.dumps(value, ensure_ascii=False)
            for key, value in metadata.items() if value is not None}


def _public_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in metadata.items()
            if key not in {"fileId", "fileName", "chunkId", "generation"}}


def _tokenize_query(query: str) -> list[str]:
    return [token for token in jieba.cut_for_search(query.lower())
            if token not in STOP_WORDS and re.fullmatch(r"[a-z0-9_\u4e00-\u9fff]+", token)]
