import re
from collections.abc import Callable, Iterator
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from cleaning import clean_text
from config import settings


SEPARATORS = ["\n\n", "\n", "\u3002", "\uff01", "\uff1f", "\uff1b", ". ", "! ", "? ", "; ", "\uff0c", " ", ""]
QUESTION = re.compile(r"^\s*(?:Q|Question|\u95ee|\u95ee\u9898)\s*[:\uff1a]\s*(.*)$", re.IGNORECASE)
ANSWER = re.compile(r"^\s*(?:A|Answer|\u7b54|\u7b54\u6848)\s*[:\uff1a]\s*(.*)$", re.IGNORECASE)


def split_text(text: str, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
    size = settings.chunk_size if chunk_size is None else chunk_size
    amount = settings.chunk_overlap if overlap is None else overlap
    if size <= 0:
        raise ValueError("chunk_size must be positive")
    if not 0 <= amount < size:
        raise ValueError("chunk_overlap must be >= 0 and < chunk_size")
    return RecursiveCharacterTextSplitter(
        chunk_size=size, chunk_overlap=amount, separators=SEPARATORS,
        keep_separator="end", strip_whitespace=True,
    ).split_text(text)


def _heading(line: str) -> tuple[int, str] | None:
    match = re.match(r"^(#{1,6})\s+(.+)$", line)
    if match:
        return len(match.group(1)), match.group(2).strip()
    if re.match(r"^\u7b2c[\u4e00-\u9fff\d]+[\u7ae0\u8282\u7bc7]\s*", line) and len(line) <= 80:
        return 1, line
    match = re.match(r"^(\d+(?:\.\d+){1,4})\s+(.{1,60})$", line)
    if match:
        return match.group(1).count(".") + 1, line
    return None


def _sections(text: str, initial_title: str, titles: list[tuple[int, str]] | None = None) -> Iterator[tuple[str, str]]:
    titles = [] if titles is None else titles
    pending = []
    for line in text.splitlines():
        heading = _heading(line.strip())
        if heading:
            if pending:
                yield " > ".join(filter(None, [initial_title, *[title for _, title in titles]])), "\n".join(pending)
                pending = []
            while titles and titles[-1][0] >= heading[0]:
                titles.pop()
            titles.append(heading)
        else:
            pending.append(line)
    title_path = " > ".join(filter(None, [initial_title, *[title for _, title in titles]]))
    if pending and "\n".join(pending).strip():
        yield title_path, "\n".join(pending)
    elif titles:
        yield title_path, titles[-1][1]


def _qa_units(text: str) -> Iterator[tuple[str, str]]:
    lines = text.splitlines()
    anchors = [i for i, line in enumerate(lines) if QUESTION.match(line)]
    if not anchors:
        yield "", text
        return
    if anchors[0]:
        yield "", "\n".join(lines[:anchors[0]])
    for start, end in zip(anchors, [*anchors[1:], len(lines)]):
        question = QUESTION.match(lines[start]).group(1)
        answer_start = next((i for i in range(start + 1, end) if ANSWER.match(lines[i])), None)
        if answer_start is None:
            yield "", "\n".join(lines[start:end])
            continue
        question = "\n".join([question, *lines[start + 1:answer_start]]).strip()
        answer = "\n".join([ANSWER.match(lines[answer_start]).group(1), *lines[answer_start + 1:end]])
        yield question, answer


def _bounded_context(text: str, count: Callable[[str], int], limit: int) -> str:
    if count(text) <= limit:
        return text
    parts = RecursiveCharacterTextSplitter(
        chunk_size=limit, chunk_overlap=0, length_function=count,
        separators=SEPARATORS, keep_separator="end",
    ).split_text(text)
    return parts[0] if parts else ""


def _split_with_context(body: str, prefix: str, count: Callable[[str], int], limit: int) -> list[str]:
    budget = limit - count(prefix) - 2
    if budget < 4:
        raise ValueError("Token budget cannot accommodate document context")
    ratio = settings.chunk_overlap / max(1, settings.chunk_size)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=budget, chunk_overlap=min(budget - 1, int(budget * ratio)),
        length_function=count, separators=SEPARATORS, keep_separator="end",
    )
    results = []
    for part in splitter.split_text(body):
        candidate = f"{prefix}{part}".strip()
        if count(candidate) <= limit:
            results.append(candidate)
            continue
        # Tokenization across a prefix boundary is not exactly additive.
        smaller = RecursiveCharacterTextSplitter(
            chunk_size=max(1, budget // 2), chunk_overlap=0,
            length_function=count, separators=SEPARATORS, keep_separator="end",
        ).split_text(part)
        if len(smaller) <= 1:
            raise ValueError("A document unit cannot fit the model token budget")
        for fragment in smaller:
            results.extend(_split_with_context(fragment, prefix, count, limit))
    return results


def split_document(
    pages: list[dict], *, token_counter: Callable[[str], int] | None = None,
    max_tokens: int | None = None, file_name: str = "",
) -> list[dict]:
    count = token_counter or len
    limit = max_tokens if max_tokens is not None else settings.chunk_size
    if limit < 16:
        raise ValueError("Document token budget must be at least 16")
    chunks = []
    document_title = Path(file_name).stem
    pdf_titles: list[tuple[int, str]] = []
    for page in pages:
        text = clean_text(page.get("text", ""))
        if not text:
            continue
        metadata = dict(page.get("metadata") or {})
        source_title = metadata.get("titlePath", "")
        if isinstance(source_title, list):
            source_title = " > ".join(source_title)
        if metadata.get("sourceType") == "txt" and not source_title:
            first_line, separator, rest = text.partition("\n")
            if separator and len(first_line) <= 50 and re.search(r"\u8001\u5e08|\u8bfe\u7a0b|\u8bb2\u4e49|\u624b\u518c|\u6307\u5357", first_line) and not re.search(r"[\u3002\uff01\uff1f.!?]", first_line):
                source_title, text = first_line, rest
        title = source_title
        for title_path, section in _sections(text, title, pdf_titles if metadata.get("sourceType") == "pdf" else None):
            for question, body in _qa_units(section):
                if not body.strip() and not question:
                    continue
                context = _bounded_context(title_path, count, max(8, limit // 4))
                prefix = f"{context}\n\n" if context else ""
                chunk_metadata = {**metadata, "titlePath": title_path, "documentTitle": document_title,
                                  "splitterVersion": "structure-v2"}
                if question:
                    chunk_metadata.update({"blockType": "qa", "question": question})
                    qa_prefix = f"{prefix}Q: {question}\nA: "
                    if count(qa_prefix) < limit // 2:
                        prefix = qa_prefix
                    else:
                        body = f"Q: {question}\nA: {body}"
                for content in _split_with_context(body, prefix, count, limit):
                    chunks.append({"chunkIndex": len(chunks) + 1, "text": content, "metadata": {
                        **chunk_metadata, "tokenCount": count(content),
                    }})
    return chunks
