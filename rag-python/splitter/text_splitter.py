from config import settings


def split_text(text: str, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
    size = chunk_size or settings.chunk_size
    step_overlap = overlap if overlap is not None else settings.chunk_overlap
    if size <= 0:
        raise ValueError("chunk_size must be positive")
    if step_overlap < 0 or step_overlap >= size:
        raise ValueError("chunk_overlap must be >= 0 and < chunk_size")

    if len(text) <= size:
        return [text] if text else []

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = end - step_overlap
    return chunks
