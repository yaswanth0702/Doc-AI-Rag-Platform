import os
from pathlib import Path

import requests
import streamlit as st

st.set_page_config(page_title="DocIntel | Reading workspace", page_icon="📖", layout="wide")
st.markdown("""
<style>
main .block-container { max-width: 68rem; padding-top: 3rem; }
[data-testid="stMainBlockContainer"] { max-width: 68rem; padding-top: 3rem; }
h1 { letter-spacing: -.035em; overflow-wrap: anywhere; }
[data-testid="stSidebar"] h2 { letter-spacing: -.025em; }
div[role="radiogroup"][aria-label="Workspace"] {
    display: flex; flex-wrap: wrap; gap: .4rem;
}
div[role="radiogroup"][aria-label="Workspace"] > label {
    padding: .4rem .85rem; margin: 0; border-radius: .5rem;
    border: 1px solid rgba(125,140,145,.45);
}
div[role="radiogroup"][aria-label="Workspace"] > label:has(input:checked) {
    background: rgba(37,154,130,.15); border-color: #368b78;
}
@media (max-width: 640px) {
    main .block-container, [data-testid="stMainBlockContainer"] { padding-inline: 1rem; }
}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("DocIntel")
    library = st.container()
    api_url = os.getenv("DOCINTEL_BACKEND_URL", "").strip().rstrip("/")
    if not api_url:
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


def bookmark_id(source):
    return source.get("chunk_id") or (source["source_name"], source.get("page"), source.get("passage") or source["snippet"])


def show_source(number, source, key):
    st.text(source_label(number, source))
    st.write(source.get("passage") or source["snippet"])
    passage_id = bookmark_id(source)
    saved = passage_id in bookmarks
    if st.button("Saved to notebook" if saved else "Save passage",
                 key=f"save:{api_url}:{selected}:{key}", disabled=saved):
        bookmarks[passage_id] = {"source": dict(source), "note": ""}
        st.rerun()


def save_note(entry, widget_key):
    entry["note"] = st.session_state[widget_key].strip()


def notebook_markdown():
    lines = [f"# {document['name']} · Reading notes"]
    for number, entry in enumerate(bookmarks.values(), 1):
        source = entry["source"]
        lines.extend(["", "## " + source_label(number, source), "", source.get("passage") or source["snippet"]])
        if entry["note"]:
            lines.extend(["", "### My note", "", entry["note"]])
    return "\n".join(lines) + "\n"


def render_turn(turn, turn_number):
    with st.chat_message("user"):
        st.write(turn["question"])
    with st.chat_message("assistant"):
        st.markdown(turn["answer"])
        sources = turn["citations"]
        if sources:
            with st.expander(f"View sources ({len(sources)})"):
                for number, source in enumerate(sources, 1):
                    show_source(number, source, f"turn:{turn_number}:{number}")
                    if number < len(sources):
                        st.divider()


def add_document():
    upload = st.file_uploader("Upload a PDF or text file", type=["pdf", "txt"])
    if st.button("Add document", type="primary", disabled=upload is None):
        with st.spinner("Indexing passages…"):
            result = post("/ingest", files={"file": (upload.name, upload.getvalue())})
        if result:
            documents[result["doc_id"]] = {
                "name": upload.name, "token": result["document_token"],
                "chunks": result["chunks_added"], "turns": [],
            }
            st.rerun()


if not documents:
    st.title("Start with a document")
    st.write("Upload a file to ask questions, check its sources, and keep reading notes.")
    with st.container(border=True):
        add_document()
    st.stop()

with library:
    st.subheader("Your documents")
    selected = st.selectbox(
        "Active document", options=list(reversed(documents)),
        format_func=lambda doc_id: f"{documents[doc_id]['name']} ({doc_id[:8]})",
        key=f"selected_document:{api_url}:{len(documents)}",
    )

    with st.expander("Add another document"):
        add_document()

document = documents[selected]
turns = document.setdefault("turns", [])
bookmarks = document.setdefault("bookmarks", {})
st.title(document["name"], anchor=False)
details = []
if "chunks" in document:
    n = document["chunks"]
    details.append(f"{n} indexed passage{'s' if n != 1 else ''}")
details.extend([f"{len(turns)} question{'s' if len(turns) != 1 else ''}",
                f"{len(bookmarks)} saved passage{'s' if len(bookmarks) != 1 else ''}"])
st.caption(" · ".join(details))

with st.sidebar:
    if turns:
        st.download_button(
            "Download conversation", transcript(document["name"], turns),
            file_name=f"{Path(document['name']).stem}-conversation.md", mime="text/markdown",
        )

view = st.radio("Workspace", ["Chat", "Find passages", "Notebook"], horizontal=True, label_visibility="collapsed")
if view == "Notebook":
    st.subheader("Reading notebook")
    if not bookmarks:
        st.info("Choose Save passage under a chat citation or search result to collect it here.")
        st.stop()
    st.download_button(
        "Download reading notes", notebook_markdown(),
        file_name=f"{Path(document['name']).stem}-notes.md", mime="text/markdown",
    )
    st.caption("Notes stay in this session. Download a copy to keep them.")
    for number, (passage_id, entry) in enumerate(bookmarks.items(), 1):
        source = entry["source"]
        key = f"{api_url}:{selected}:{passage_id}"
        with st.container(border=True):
            st.text(source_label(number, source))
            st.write(source.get("passage") or source["snippet"])
            with st.form(f"note:{key}"):
                widget_key = f"draft:{key}"
                st.text_area("My note", value=entry["note"], key=widget_key,
                             placeholder="Add an observation or a follow-up question.")
                st.form_submit_button("Save note", on_click=save_note, args=(entry, widget_key))
            st.button("Remove from notebook", key=f"remove:{key}",
                      on_click=bookmarks.pop, args=(passage_id, None))
    st.stop()

if view == "Find passages":
    with st.form(f"search:{api_url}:{selected}"):
        search_query = st.text_input("Search this document", placeholder="Enter a concept, name, or reference code")
        mode = st.radio("Search method", ["Hybrid", "Exact phrase"], horizontal=True,
                        help="Hybrid combines meaning and keywords. Exact phrase matches text across spaces and line breaks.")
        page = None
        if Path(document["name"]).suffix.lower() == ".pdf":
            page = st.number_input("PDF page (optional)", min_value=1, value=None, step=1, placeholder="All pages")
        submitted = st.form_submit_button("Find passages", type="primary")
    if submitted:
        query = search_query.strip()
        if query:
            payload = {"doc_id": selected, "query": query, "mode": "exact" if mode == "Exact phrase" else "hybrid"}
            if page is not None:
                payload["page"] = page
            with st.spinner("Searching this document…"):
                result = post(
                    "/search", json=payload,
                    headers={"Authorization": f"Bearer {document['token']}"},
                )
            if result is not None:
                document["search"] = {"query": query, "mode": mode, "page": page, "passages": result["passages"]}
        else:
            st.info("Enter a phrase or topic to search.")
    last_search = document.get("search")
    if last_search:
        scope = f" · Page {last_search['page']}" if last_search.get("page") is not None else ""
        st.caption(f"{last_search['mode']} results for “{last_search['query']}”{scope}")
        if not last_search["passages"]:
            if last_search.get("page") is not None:
                st.info("No matching passages on this page. Clear the page field to search the full document.")
            else:
                st.info("No matching passages. Try a shorter phrase or switch to Hybrid.")
        if last_search["passages"]:
            lines = [f"# {document['name']}", "", f"Search: {last_search['query']}",
                     f"Method: {last_search['mode']}{scope}"]
            for number, source in enumerate(last_search["passages"], 1):
                lines.extend(["", "## " + source_label(number, source), "", source["passage"]])
            st.download_button(
                "Download search results", "\n".join(lines) + "\n",
                file_name=f"{Path(document['name']).stem}-search.md", mime="text/markdown",
            )
        for number, source in enumerate(last_search["passages"], 1):
            with st.container(border=True):
                show_source(number, source, f"search:{number}")
    st.stop()

if not turns:
    st.caption("Ask your first question below, or open Find passages to search the document directly.")
for turn_number, turn in enumerate(turns):
    render_turn(turn, turn_number)

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
