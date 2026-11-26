import requests
import streamlit as st

st.set_page_config(page_title="DocIntel-RAG (Gemini)", layout="wide")
api_url = st.sidebar.text_input("Backend URL", value="http://localhost:8000").rstrip("/")
st.title("📄 DocIntel-RAG (Gemini): PDF Chat with Citations")

# Keep each backend's document credentials in this Streamlit session.
documents = st.session_state.setdefault("documents", {}).setdefault(api_url, {})


def post(path, **kwargs):
    try:
        response = requests.post(f"{api_url}{path}", timeout=300, **kwargs)
        if response.ok:
            return response.json()
        try:
            detail = response.json().get("detail", response.reason)
        except ValueError:
            detail = response.reason
        st.error(f"Request failed ({response.status_code}): {detail}")
    except (requests.RequestException, ValueError):
        st.error("Could not reach the backend or read its response.")
    return None


with st.sidebar:
    st.subheader("1) Upload a document")
    upload = st.file_uploader("PDF or TXT", type=["pdf", "txt"])
    if st.button("Ingest", disabled=upload is None):
        result = post("/ingest", files={"file": (upload.name, upload.getvalue())})
        if result:
            doc_id = result["doc_id"]
            documents[doc_id] = {"name": upload.name, "token": result["document_token"]}
            st.success(f"Indexed {result['chunks_added']} passages.")

    selected = None
    if documents:
        selected = st.selectbox(
            "Document to ask about", options=list(reversed(documents)),
            format_func=lambda doc_id: f"{documents[doc_id]['name']} ({doc_id[:8]})",
            key=f"selected_document:{api_url}:{len(documents)}",
        )

st.subheader("2) Ask a question")
question = st.text_input("Question", placeholder="Ask about the selected document")
if st.button("Ask", disabled=not selected or not question.strip()):
    result = post(
        "/ask",
        json={"question": question, "doc_id": selected},
        headers={"Authorization": f"Bearer {documents[selected]['token']}"},
    )
    if result:
        st.markdown("### Answer")
        st.write(result["answer"])
        if result["citations"]:
            st.markdown("### Citations")
        for citation in result["citations"]:
            page = citation["page"] or "n/a"
            st.write(f"{citation['source_name']} · page {page} · score {citation['score']:.3f}")
            st.caption(citation["chunk_id"])
            st.write(citation["snippet"])
