import streamlit as st
import requests

st.set_page_config(page_title="DocIntel-RAG (Gemini)", layout="wide")

API_URL = st.sidebar.text_input("Backend URL", value="http://localhost:8000")

st.title("📄 DocIntel-RAG (Gemini): PDF Chat with Citations")

with st.sidebar:
    st.subheader("1) Upload a document")
    up = st.file_uploader("PDF or TXT", type=["pdf", "txt"])
    if st.button("Ingest") and up is not None:
        files = {"file": (up.name, up.getvalue())}
        r = requests.post(f"{API_URL}/ingest", files=files, timeout=300)
        if r.status_code == 200:
            data = r.json()
            st.success(f"Ingested ✅ doc_id={data['doc_id']} chunks={data['chunks_added']}")
        else:
            st.error(r.text)

st.subheader("2) Ask a question")
q = st.text_input("Question", placeholder="Ask something that is present in the PDF…")

if st.button("Ask") and q.strip():
    r = requests.post(f"{API_URL}/ask", json={"question": q}, timeout=300)
    if r.status_code != 200:
        st.error(r.text)
    else:
        data = r.json()
        st.markdown("### Answer")
        st.write(data["answer"])

        st.markdown("### Citations")
        for c in data["citations"]:
            page = c["page"] if c["page"] is not None else "n/a"
            st.markdown(
                f"- **{c['source_name']}** (page {page}) score={c['score']:.3f}\n\n"
                f"  `{c['chunk_id']}`\n\n"
                f"  _{c['snippet']}_"
            )
