import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .models import IngestResponse, AskRequest, AskResponse, Citation
from .rag.ingest import build_chunks_from_file
from .rag.embedder import Embedder
from .rag.vector_store import FaissStore
from .rag.retriever import Retriever
from .rag.generator import generate_answer
from .rag.guardrails import guard_question

app = FastAPI(title="DocIntel-RAG (Gemini)", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(settings.index_dir, exist_ok=True)
os.makedirs(settings.uploads_dir, exist_ok=True)

embedder = Embedder(settings.embedding_model)
store = FaissStore(settings.index_dir)
retriever = Retriever(store, embedder, top_k=settings.top_k)

@app.get("/health")
def health():
    return {"status": "ok", "llm_provider": settings.llm_provider, "gemini_model": settings.gemini_model}

@app.post("/ingest", response_model=IngestResponse)
async def ingest(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".pdf", ".txt"]:
        raise HTTPException(status_code=400, detail="Only .pdf or .txt supported")

    save_path = os.path.join(settings.uploads_dir, file.filename)
    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    doc_id, chunks = build_chunks_from_file(save_path, source_name=file.filename)
    if not chunks:
        raise HTTPException(status_code=400, detail="No text extracted from file")

    texts = [c["text"] for c in chunks]
    vecs = embedder.embed_texts(texts)

    metas = [{
        "doc_id": c["doc_id"],
        "source_name": c["source_name"],
        "page": c["page"],
        "chunk_id": c["chunk_id"],
        "text": c["text"],
    } for c in chunks]

    added = store.add(vecs, metas)
    return IngestResponse(doc_id=doc_id, chunks_added=added)

@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    ok, msg = guard_question(req.question)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    retrieved = retriever.retrieve(req.question)
    answer = generate_answer(req.question, retrieved)

    citations = []
    for r in retrieved:
        snippet = r.get("text", "")
        if len(snippet) > 220:
            snippet = snippet[:220] + "…"
        citations.append(Citation(
            doc_id=r.get("doc_id"),
            source_name=r.get("source_name"),
            page=r.get("page"),
            chunk_id=r.get("chunk_id"),
            score=float(r.get("score", 0.0)),
            snippet=snippet
        ))

    debug = {
        "top_k": settings.top_k,
        "embedding_model": settings.embedding_model,
        "llm_provider": settings.llm_provider,
        "gemini_model": settings.gemini_model,
    }

    return AskResponse(answer=answer, citations=citations, debug=debug)
