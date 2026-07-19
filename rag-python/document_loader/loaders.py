from pathlib import Path


SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".docx"}


def load_document(file_path: str) -> list[dict]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"file not found: {file_path}")

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(f"unsupported file type: {suffix}; supported: {supported}")

    if suffix == ".txt":
        return _load_txt(path)
    if suffix == ".pdf":
        return _load_pdf(path)
    if suffix == ".docx":
        return _load_docx(path)

    raise ValueError(f"unsupported file type: {suffix}")


def _load_txt(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="gbk", errors="ignore")
    return [{"text": text, "metadata": {"sourceType": "txt"}}]


def _load_pdf(path: Path) -> list[dict]:
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("pdfplumber is required to parse pdf files") from exc

    pages = []
    with pdfplumber.open(str(path)) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages.append({"text": text, "metadata": {"sourceType": "pdf", "page": index}})
    return pages


def _load_docx(path: Path) -> list[dict]:
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("python-docx is required to parse docx files") from exc

    document = Document(str(path))
    paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    text = "\n".join(paragraphs)
    return [{"text": text, "metadata": {"sourceType": "docx"}}]
