import os
from typing import List, Dict, Any

from pypdf import PdfReader
from pypdf.errors import PyPdfError
from .chunking import chunk_text, clean_text

def read_pdf_pages(path: str) -> List[Dict[str, Any]]:
    reader = PdfReader(path)
    pages = []
    for i, page in enumerate(reader.pages):
        txt = page.extract_text() or ""
        pages.append({"page": i + 1, "text": clean_text(txt)})
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
