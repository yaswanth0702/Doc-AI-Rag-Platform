from pydantic import BaseModel, Field
from uuid import UUID
from typing import List, Optional, Dict, Any

class IngestResponse(BaseModel):
    doc_id: str
    document_token: str
    chunks_added: int

class PreviousTurn(BaseModel):
    question: str = Field(..., min_length=1, max_length=600)
    answer: str = Field(..., min_length=1, max_length=1200)

class AskRequest(BaseModel):
    doc_id: Optional[UUID] = None
    previous_turn: Optional[PreviousTurn] = None
    question: str = Field(..., min_length=1)

class Citation(BaseModel):
    doc_id: str
    source_name: str
    page: Optional[int] = None
    chunk_id: str
    score: float
    snippet: str
    passage: Optional[str] = None

class AskResponse(BaseModel):
    answer: str
    citations: List[Citation]
    debug: Optional[Dict[str, Any]] = None
