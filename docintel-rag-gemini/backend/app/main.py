import hashlib
import secrets
import shutil
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID, uuid4

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .models import AskRequest, AskResponse, Citation, IngestResponse
from .rag.embedder import Embedder
from .rag.generator import GenerationUnavailable, generate_answer
from .rag.guardrails import guard_question
from .rag.ingest import build_chunks_from_file
from .rag.retriever import Retriever
from .rag.vector_store import FaissStore

app = FastAPI(title="DocIntel-RAG (Gemini)", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    return Embedder(settings.embedding_model)


def index_path(doc_id: UUID, token: str) -> Path:
    # Bind this immutable document version to the secret issued at upload.
    digest = hashlib.sha256(token.encode()).hexdigest()
    return Path(settings.index_dir) / f"{doc_id}-{digest}"


@app.get("/health")
def health():
    return {"status": "ok", "llm_provider": "gemini", "gemini_model": settings.gemini_model}


@app.post("/ingest", response_model=IngestResponse)
def ingest(file: UploadFile = File(...)):
    source_name = Path((file.filename or "").replace("\\", "/")).name
    ext = Path(source_name).suffix.lower()
    if ext not in {".pdf", ".txt"}:
        raise HTTPException(400, "Only .pdf or .txt supported")

    doc_id = uuid4()
    token = secrets.token_urlsafe(32)
    destination = index_path(doc_id, token)
    uploads = Path(settings.uploads_dir)
    uploads.mkdir(parents=True, exist_ok=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    original = uploads / f"{doc_id}{ext}"

    # Each upload owns its paths. Publish the index only after every write succeeds.
    with TemporaryDirectory(dir=destination.parent) as staging:
        staged_index = Path(staging) / "index"
        output = original.open("xb")
        try:
            with output:
                shutil.copyfileobj(file.file, output)
            try:
                chunks = build_chunks_from_file(str(original), source_name, str(doc_id))
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
            if not chunks:
                raise HTTPException(400, "No text extracted from file")

            vectors = get_embedder().embed_texts([chunk["text"] for chunk in chunks])
            added = FaissStore(str(staged_index)).add(vectors, chunks)
            staged_index.rename(destination)
        except BaseException:
            original.unlink(missing_ok=True)
            raise
    return IngestResponse(doc_id=str(doc_id), document_token=token, chunks_added=added)


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest, authorization: str | None = Header(default=None)):
    ok, msg = guard_question(req.question)
    if not ok:
        raise HTTPException(400, msg)
    if req.doc_id is None:
        return AskResponse(answer="Upload and select a document before asking a question.", citations=[])

    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "A document access token is required.", headers={"WWW-Authenticate": "Bearer"})
    path = index_path(req.doc_id, token)
    if not path.is_dir():
        raise HTTPException(404, "Document unavailable.")

    retriever = Retriever(FaissStore(str(path)), get_embedder(), top_k=settings.top_k)
    query = req.question
    if req.previous_turn:
        query = f"{req.question}\nPrevious question: {req.previous_turn.question[:240]}\n{req.previous_turn.answer[:320]}"
    retrieved = retriever.retrieve(query)
    if not retrieved:
        return AskResponse(answer="No passages were found in this document.", citations=[])
    try:
        answer = generate_answer(req.question, retrieved, req.previous_turn)
    except GenerationUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc

    citations = []
    for r in retrieved:
        snippet = r["text"]
        if len(snippet) > 220:
            snippet = snippet[:220] + "…"
        citations.append(Citation(
            doc_id=r["doc_id"], source_name=r["source_name"], page=r.get("page"),
            chunk_id=r["chunk_id"], score=r["score"], snippet=snippet, passage=r["text"],
        ))

    return AskResponse(answer=answer, citations=citations, debug={
        "top_k": settings.top_k, "embedding_model": settings.embedding_model,
        "llm_provider": "gemini", "gemini_model": settings.gemini_model,
    })
