from pathlib import Path

import requests
import streamlit as st

st.set_page_config(page_title="DocIntel | Document chat", page_icon="📖", layout="centered")
with st.sidebar:
    st.header("DocIntel")
    with st.expander("Connection settings"):
        api_url = st.text_input("Backend URL", value="http://localhost:8000").rstrip("/")

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


def source_label(number, source):
    label = f"[{number}] {source['source_name']}"
    if source.get("page") is not None:
        label += f" · Page {source['page']}"
    return label


def transcript(name, turns):
    lines = [f"# {name}"]
    for turn in turns:
        lines.extend(["", "## Question", "", turn["question"], "", "## Answer", "", turn["answer"]])
        if turn["citations"]:
            lines.extend(["", "### Sources"])
        for number, source in enumerate(turn["citations"], 1):
            lines.extend(["", source_label(number, source), "", source.get("passage") or source["snippet"]])
    return "\n".join(lines) + "\n"


def render_turn(turn):
    with st.chat_message("user"):
        st.write(turn["question"])
    with st.chat_message("assistant"):
        st.markdown(turn["answer"])
        sources = turn["citations"]
        if sources:
            with st.expander(f"View sources ({len(sources)})"):
                for number, source in enumerate(sources, 1):
                    st.text(source_label(number, source))
                    st.write(source.get("passage") or source["snippet"])
                    if number < len(sources):
                        st.divider()


with st.sidebar:
    st.subheader("Documents")
    upload = st.file_uploader("Upload a PDF or text file", type=["pdf", "txt"])
    if st.button("Add document", type="primary", disabled=upload is None):
        with st.spinner("Indexing passages…"):
            result = post("/ingest", files={"file": (upload.name, upload.getvalue())})
        if result:
            documents[result["doc_id"]] = {
                "name": upload.name, "token": result["document_token"],
                "chunks": result["chunks_added"], "turns": [],
            }

    selected = None
    if documents:
        selected = st.selectbox(
            "Active document", options=list(reversed(documents)),
            format_func=lambda doc_id: f"{documents[doc_id]['name']} ({doc_id[:8]})",
            key=f"selected_document:{api_url}:{len(documents)}",
        )

if selected is None:
    st.title("Document chat")
    st.info("Add a PDF or text file in the sidebar to ask questions and read the passages behind each answer.")
    st.stop()

document = documents[selected]
turns = document.setdefault("turns", [])
st.title(document["name"], anchor=False)
if "chunks" in document:
    count = document["chunks"]
    st.caption(f"{count} indexed passage{'s' if count != 1 else ''} · Chat saved for this session")

with st.sidebar:
    if turns:
        st.download_button(
            "Download conversation", transcript(document["name"], turns),
            file_name=f"{Path(document['name']).stem}-conversation.md", mime="text/markdown",
        )

view = st.radio("Workspace", ["Chat", "Find passages"], horizontal=True, label_visibility="collapsed")
if view == "Find passages":
    with st.form(f"search:{api_url}:{selected}"):
        search_query = st.text_input("Search this document", placeholder="Enter a concept, name, or reference code")
        mode = st.radio("Search method", ["Hybrid", "Exact phrase"], horizontal=True,
                        help="Hybrid combines meaning and keywords. Exact phrase matches text across spaces and line breaks.")
        submitted = st.form_submit_button("Find passages", type="primary")
    if submitted:
        query = search_query.strip()
        if query:
            with st.spinner("Searching this document…"):
                result = post(
                    "/search", json={"doc_id": selected, "query": query, "mode": "exact" if mode == "Exact phrase" else "hybrid"},
                    headers={"Authorization": f"Bearer {document['token']}"},
                )
            if result is not None:
                document["search"] = {"query": query, "mode": mode, "passages": result["passages"]}
        else:
            st.info("Enter a phrase or topic to search.")
    last_search = document.get("search")
    if last_search:
        st.caption(f"{last_search['mode']} results for “{last_search['query']}”")
        if not last_search["passages"]:
            st.info("No matching passages. Try a shorter phrase or switch to Hybrid.")
        for number, source in enumerate(last_search["passages"], 1):
            with st.container(border=True):
                st.text(source_label(number, source))
                st.write(source["passage"])
    st.stop()

for turn in turns:
    render_turn(turn)

follow_up = False
if turns:
    follow_up = st.toggle(
        "Use the previous exchange for this question",
        help="Turn this on for a follow-up such as “Which of those happens first?”",
        key=f"follow_up:{api_url}:{selected}:{len(turns)}",
    )
question = st.chat_input("Ask about this document", key=f"question:{api_url}:{selected}")
if question and question.strip():
    question = question.strip()
    payload = {"question": question, "doc_id": selected}
    if follow_up:
        previous = turns[-1]
        payload["previous_turn"] = {"question": previous["question"][:600], "answer": previous["answer"][:1200]}
    with st.spinner("Finding relevant passages…"):
        result = post("/ask", json=payload, headers={"Authorization": f"Bearer {document['token']}"})
    if result:
        turns.append({"question": question, "answer": result["answer"], "citations": result["citations"]})
        st.rerun()
    else:
        st.caption("Your question was not added to this conversation.")
        st.code(question, language=None)
