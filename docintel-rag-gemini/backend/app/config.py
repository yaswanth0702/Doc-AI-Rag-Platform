
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    # Paths (relative to backend/ when running)
    index_dir: str = os.getenv("INDEX_DIR", "app/storage/index")
    uploads_dir: str = os.getenv("UPLOADS_DIR", "app/storage/uploads")

    # Retrieval
    top_k: int = int(os.getenv("TOP_K", "6"))

    # Embeddings (local)
    embedding_model: str = os.getenv(
        "EMBEDDING_MODEL",
        "sentence-transformers/all-MiniLM-L6-v2"
    )

    # Gemini
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

settings = Settings()
