# DocIntel-RAG (Gemini)

Upload a PDF or text file, ask questions about it, and inspect the retrieved passages and page numbers. FastAPI extracts and chunks the text, SentenceTransformers embeds the chunks locally, and FAISS indexes each document separately. Gemini receives the question and the selected passages to generate the answer.

## Run locally

Use Python 3.11 or 3.12. From the repository root on macOS or Linux:

```bash
cd docintel-rag-gemini/backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -r ../ui/requirements.txt
export GEMINI_API_KEY="your-key-from-Google-AI-Studio"
python -m uvicorn app.main:app --port 8000
```

On Windows PowerShell, activate the environment with `.\.venv\Scripts\Activate.ps1` and set the key with `$env:GEMINI_API_KEY = "your-key-from-Google-AI-Studio"`. The first upload downloads the embedding model. The backend reads process environment variables. Set `GEMINI_MODEL` to override the default `gemini-flash-latest`.

In a second terminal, start from the repository root:

```bash
cd docintel-rag-gemini/backend
.venv/bin/python -m streamlit run ../ui/streamlit_app.py
```

On Windows use `.\.venv\Scripts\python.exe` in the last command. Open the Streamlit address shown in the terminal, upload a file, click **Add document**, then ask a question about the selected document.

## API and existing documents

- `POST /ingest` accepts a multipart field named `file` and returns `doc_id`, `document_token`, and `chunks_added`. Each successful upload creates a separate version, including uploads with the same filename.
- `POST /ask` accepts `{"doc_id": "<id>", "question": "What does the document say?"}`. Send `Authorization: Bearer <document_token>` from the matching upload. Anyone holding both values can query that document. Use HTTPS when accessing a remote backend.
- The Streamlit document selector remembers uploads for the current browser session. API clients can retain the ID and token to ask again after a restart. If you lose the token, upload the file again.
- Documents indexed by older versions have no access token. Re-upload their originals to use them with this version. The old index and files stay on disk.
- `GET /health` returns the configured model and provider. Gemini access is checked when generating an answer.

## Run the regression tests

From the backend directory with the environment active:

```bash
python -m pip install httpx==0.27.2
python -m unittest discover -s tests
```

The tests use temporary storage and local FAISS indexes. Embeddings and Gemini responses are supplied by the tests so they can run offline.

## Working with a document

Each document version has its own conversation in the current Streamlit session. Open **View sources** beneath an answer to match its numbered references to the retrieved passages. PDF sources include page numbers. Switch documents in the sidebar to return to an earlier conversation.

For a follow-up, turn on **Use the previous exchange for this question**. The backend uses the last question and answer to interpret the new question and retrieves evidence from the active document. Direct API callers can send an optional `previous_turn` object with `question` (up to 600 characters) and `answer` (up to 1,200 characters). Each citation includes the original `snippet` and the full retrieved `passage`.

Choose **Download conversation** to save the active transcript and its source passages as Markdown before ending the browser session.
