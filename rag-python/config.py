from pathlib import Path

try:
    from pydantic_settings import BaseSettings
except ImportError:
    class BaseSettings:
        def __init__(self, **values):
            for key, value in self.__class__.__dict__.items():
                if key.startswith("_") or callable(value):
                    continue
                setattr(self, key, values.get(key, value))


BASE_DIR = Path(__file__).resolve().parent


def _resolve_path_from_module(path_value: str) -> str:
    path = Path(path_value)
    if path.is_absolute():
        return str(path)
    return str((BASE_DIR / path).resolve())


class Settings(BaseSettings):
    app_name: str = "rag-qa-service"
    vector_store_path: str = "storage/vector_store"
    collection_name: str = "rag_chunks"
    embedding_model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dimension: int = 384
    chunk_size: int = 800
    chunk_overlap: int = 120
    default_top_k: int = 5

    def __init__(self, **values):
        super().__init__(**values)
        self.vector_store_path = _resolve_path_from_module(self.vector_store_path)


settings = Settings()
