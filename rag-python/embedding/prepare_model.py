"""Explicit model download; normal API requests only load local files."""

from huggingface_hub import snapshot_download

from config import settings
from embedding import EmbeddingProvider


def main() -> None:
    print(f"Preparing {settings.embedding_model_name} in project storage", flush=True)
    snapshot_download(
        repo_id=settings.embedding_model_name,
        local_dir=settings.embedding_local_path,
        allow_patterns=["*.json", "*.txt", "*.model", "model.safetensors", "1_Pooling/*"],
        max_workers=2,
    )
    provider = EmbeddingProvider()
    provider.embed(["local semantic embedding verification"])
    print(f"Ready: dimension={provider.dimension}, maxTokens={provider.max_input_tokens}, "
          f"fingerprint={provider.model_fingerprint}", flush=True)


if __name__ == "__main__":
    main()
