from pydantic import BaseModel, Field
from uuid import UUID
from typing import List, Optional, Dict, Any, Literal, Annotated
from pydantic import StringConstraints

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

class SearchRequest(BaseModel):
    doc_id: UUID
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    mode: Literal["hybrid", "exact"] = "hybrid"
    limit: int = Field(default=6, ge=1, le=20)
    page: int | None = Field(default=None, ge=1, strict=True)

class Passage(BaseModel):
    doc_id: str
    source_name: str
    page: Optional[int] = None
    chunk_id: str
    snippet: str
    passage: Optional[str] = None

class Citation(Passage):
    score: float

class SearchResponse(BaseModel):
    passages: List[Passage]

class AskResponse(BaseModel):
    answer: str
    citations: List[Citation]
    debug: Optional[Dict[str, Any]] = None
