
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class IngestResponse(BaseModel):
    doc_id: str
    chunks_added: int

class AskRequest(BaseModel):
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
