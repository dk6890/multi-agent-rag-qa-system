from pathlib import Path
from collections import Counter
import codecs
import re

from cleaning import clean_text


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
    blob = path.read_bytes()
    for bom, codec in ((codecs.BOM_UTF32_LE, "utf-32"), (codecs.BOM_UTF32_BE, "utf-32"),
                       (codecs.BOM_UTF16_LE, "utf-16"), (codecs.BOM_UTF16_BE, "utf-16"),
                       (codecs.BOM_UTF8, "utf-8-sig")):
        if blob.startswith(bom):
            return [{"text": blob.decode(codec), "metadata": {"sourceType": "txt", "encoding": codec}}]
    try:
        text, codec = blob.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        from charset_normalizer import from_bytes

        detected = from_bytes(blob).best()
        if detected is not None and detected.encoding.replace("_", "-") in {"utf-16-le", "utf-16-be", "utf-16"}:
            return [{"text": blob.decode(detected.encoding), "metadata": {"sourceType": "txt", "encoding": detected.encoding}}]
        try:
            text, codec = blob.decode("gb18030"), "gb18030"
        except UnicodeDecodeError as exc:
            raise ValueError("Unsupported or damaged TXT encoding; save it as UTF-8") from exc
    if "\x00" in text:
        raise ValueError("TXT contains NUL bytes; use UTF-8 or UTF-16 with a BOM")
    return [{"text": text, "metadata": {"sourceType": "txt", "encoding": codec}}]


def _table_rows(rows: list[list]) -> str:
    nonempty = [[clean_text("" if value is None else str(value)) for value in row] for row in rows if row]
    if not nonempty:
        return ""
    if len(nonempty) == 1:
        return " | ".join(nonempty[0])
    headers = [value or f"column {i + 1}" for i, value in enumerate(nonempty[0])]
    return " | ".join(headers) + "\n" + "\n".join(
        "; ".join(f"{headers[i] if i < len(headers) else f'column {i + 1}'}: {value}"
                  for i, value in enumerate(row) if value)
        for row in nonempty[1:] if any(row)
    )


def _load_pdf(path: Path) -> list[dict]:
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("pdfplumber is required to parse pdf files") from exc

    pages = []
    with pdfplumber.open(str(path)) as pdf:
        margins = []
        for page in pdf.pages:
            band = min(45, page.height * 0.08)
            top = clean_text(page.crop((0, 0, page.width, band)).extract_text() or "")
            bottom = clean_text(page.crop((0, page.height - band, page.width, page.height)).extract_text() or "")
            margins.append((top, bottom))
        frequency = Counter(line for pair in margins
                            for line in set("\n".join(pair).splitlines()) if 4 <= len(line) < 80)
        repeated = {line for line, count in frequency.items()
                    if len(pdf.pages) >= 3 and count >= max(3, len(pdf.pages) * 0.6)}
        for index, page in enumerate(pdf.pages, start=1):
            tables = sorted(page.find_tables(), key=lambda table: table.bbox[1])
            cursor = float(page.bbox[1])
            blocks = []
            for table in tables:
                left, top, right, bottom = table.bbox
                if top > cursor:
                    text = page.crop((page.bbox[0], cursor, page.bbox[2], top)).extract_text() or ""
                    blocks.append((text, "text"))
                # Keep text beside a table, instead of dropping the entire horizontal band.
                beside = page.filter(lambda obj: not (
                    obj.get("object_type") == "char"
                    and left <= (obj["x0"] + obj["x1"]) / 2 <= right
                    and top <= (obj["top"] + obj["bottom"]) / 2 <= bottom
                )).crop((page.bbox[0], top, page.bbox[2], bottom)).extract_text() or ""
                if beside.strip():
                    blocks.append((beside, "text"))
                blocks.append((_table_rows(table.extract()), "table"))
                cursor = max(cursor, bottom)
            if cursor < page.bbox[3]:
                blocks.append((page.crop((page.bbox[0], cursor, page.bbox[2], page.bbox[3])).extract_text() or "", "text"))
            for text, block_type in blocks:
                # Only recognized margin strings are removed; ordinary repeated body text stays.
                lines = text.splitlines()
                if block_type == "text":
                    while lines and lines[0].strip() in repeated:
                        lines.pop(0)
                    while lines and lines[-1].strip() in repeated:
                        lines.pop()
                text = "\n".join(lines)
                if text.strip():
                    pages.append({"text": text, "metadata": {"sourceType": "pdf", "page": index, "blockType": block_type}})
    if not pages:
        raise ValueError("PDF has no extractable text; scanned PDFs require OCR before indexing")
    return pages


def _load_docx(path: Path) -> list[dict]:
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("python-docx is required to parse docx files") from exc

    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = Document(str(path))
    blocks = []
    titles: list[tuple[int, str]] = []
    pending: list[str] = []

    def flush() -> None:
        if pending:
            blocks.append({"text": "\n\n".join(pending), "metadata": {
                "sourceType": "docx", "blockType": "text",
                "titlePath": " > ".join(title for _, title in titles),
            }})
            pending.clear()

    for element in document.element.body:
        if element.tag.endswith("}p"):
            paragraph = Paragraph(element, document)
            text = paragraph.text.strip()
            if not text:
                continue
            style = paragraph.style.name if paragraph.style else ""
            heading = re.match(r"(?:Heading|\u6807\u9898)\s*(\d+)$", style, re.IGNORECASE)
            if heading:
                flush()
                level = int(heading.group(1))
                while titles and titles[-1][0] >= level:
                    titles.pop()
                titles.append((level, text))
            else:
                pending.append(text)
        elif element.tag.endswith("}tbl"):
            flush()
            table = Table(element, document)
            text = _table_rows([[cell.text for cell in row.cells] for row in table.rows])
            if text:
                blocks.append({"text": text, "metadata": {
                    "sourceType": "docx", "blockType": "table",
                    "titlePath": " > ".join(title for _, title in titles),
                }})
    flush()
    if not blocks and titles:
        blocks.append({"text": "\n".join(title for _, title in titles),
                       "metadata": {"sourceType": "docx", "blockType": "text"}})
    return blocks
