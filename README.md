# Doc-AI-Rag-Platform

# DocIntel-RAG (Gemini)

A PDF-reading RAG app:
- Upload PDF/TXT
- Chunk + embed (SentenceTransformers)
- Retrieve top-k with FAISS
- Generate grounded answers with Gemini
- Return citations with page + chunk_id

## Tech
- FastAPI backend
- SentenceTransformers embeddings (local)
- FAISS vector search (local)
- Gemini API (generation)
- Optional Streamlit UI

---

## 1) Get Gemini API Key
Create an API key in Google AI Studio and copy it.

---

## 2) Run backend (local)

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
