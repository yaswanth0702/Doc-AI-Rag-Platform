import os
import re
from typing import List, Dict, Any

from pypdf import PdfReader
from pypdf.errors import PyPdfError
from .chunking import chunk_text, clean_text

def recover_pdf_spacing(page, text: str) -> str:
    """Use layout positions to recover missing spaces, retaining plain reading order."""
    if not text.strip():
        return text
    try:
        layout = page.extract_text(extraction_mode="layout", layout_mode_space_vertically=False)
    except (PyPdfError, ValueError, KeyError, IndexError, TypeError, ZeroDivisionError):
        return text

    # Columns and rotated text can produce different reading orders. Only transfer
    # word boundaries when both extractors agree on every non-whitespace character.
    if not layout or "".join(layout.split()) != "".join(text.split()):
        return text
    boundaries = set()
    offset = 0
    for word in layout.split():
        offset += len(word)
        boundaries.add(offset)

    pieces = []
    offset = 0
    for token in re.findall(r"\s+|\S+", text):
        if token.isspace():
            pieces.append(token)
            continue
        for i, char in enumerate(token):
            if i and offset in boundaries:
                pieces.append(" ")
            pieces.append(char)
            offset += 1
    return "".join(pieces)


def read_pdf_pages(path: str) -> List[Dict[str, Any]]:
    reader = PdfReader(path)
    pages = []
    for i, page in enumerate(reader.pages):
        txt = page.extract_text() or ""
        pages.append({"page": i + 1, "text": clean_text(recover_pdf_spacing(page, txt))})
    return pages

def read_txt(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return clean_text(f.read())

def build_chunks_from_file(file_path: str, source_name: str, doc_id: str) -> List[Dict[str, Any]]:
    ext = os.path.splitext(file_path)[1].lower()

    chunks: List[Dict[str, Any]] = []

    if ext == ".pdf":
        try:
            pages = read_pdf_pages(file_path)
        except (PyPdfError, ValueError, KeyError, IndexError, EOFError) as exc:
            raise ValueError("Cannot read this PDF. Upload a readable, unlocked PDF.") from exc
        for p in pages:
            page_no = p["page"]
            for idx, ch in enumerate(chunk_text(p["text"])):
                chunks.append({
                    "doc_id": doc_id,
                    "source_name": source_name,
                    "page": page_no,
                    "chunk_id": f"{doc_id}_p{page_no}_c{idx}",
                    "text": ch,
                })
    else:
        text = read_txt(file_path)
        for idx, ch in enumerate(chunk_text(text)):
            chunks.append({
                "doc_id": doc_id,
                "source_name": source_name,
                "page": None,
                "chunk_id": f"{doc_id}_c{idx}",
                "text": ch,
            })

    return chunks
