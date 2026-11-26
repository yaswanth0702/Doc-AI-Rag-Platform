from pydantic import BaseModel, Field
from uuid import UUID
from typing import List, Optional, Dict, Any

class IngestResponse(BaseModel):
    doc_id: str
    document_token: str
    chunks_added: int

class AskRequest(BaseModel):
    doc_id: Optional[UUID] = None
    question: str = Field(..., min_length=1)

class Citation(BaseModel):
    doc_id: str
    source_name: str
    page: Optional[int] = None
    chunk_id: str
    score: float
    snippet: str

class AskResponse(BaseModel):
    answer: str
    citations: List[Citation]
    debug: Optional[Dict[str, Any]] = None
