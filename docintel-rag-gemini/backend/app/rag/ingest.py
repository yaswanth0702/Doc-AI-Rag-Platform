import os
import uuid
from typing import List, Dict, Any, Tuple

from pypdf import PdfReader
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

def build_chunks_from_file(file_path: str, source_name: str) -> Tuple[str, List[Dict[str, Any]]]:
    doc_id = str(uuid.uuid4())
    ext = os.path.splitext(file_path)[1].lower()

    chunks: List[Dict[str, Any]] = []

    if ext == ".pdf":
        pages = read_pdf_pages(file_path)
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

    return doc_id, chunks
