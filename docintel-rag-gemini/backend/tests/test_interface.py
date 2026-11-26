import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import streamlit as st
from streamlit.testing.v1 import AppTest


class InterfaceTests(unittest.TestCase):
    def test_chats_and_downloads_follow_the_selected_document(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[2] / "ui" / "streamlit_app.py")).run()
        self.assertEqual(len(app.chat_input), 0)
        self.assertFalse(app.exception)
        app.session_state["documents"] = {"http://localhost:8000": {
            "first": {"name": "lecture.txt", "token": "first-token"},
            "second": {"name": "paper.pdf", "token": "second-token"},
        }}
        app.run()
        source = {"source_name": "paper.pdf", "page": 4, "snippet": "Short", "passage": "Full source text"}
        response = Mock()
        response.json.return_value = {"answer": "Thirty days [1].", "citations": [source]}
        with patch("requests.post", return_value=response) as request, patch.object(
            st, "download_button", wraps=st.download_button
        ) as download:
            app.chat_input[0].set_value("What is the deadline?").run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.chat_message), 2)
            self.assertTrue(any("[1] paper.pdf · Page 4" in item.value for item in app.text))
            exported = download.call_args.args[1]
            for expected in ("What is the deadline?", "Thirty days [1].", "Full source text"):
                self.assertIn(expected, exported)
            self.assertNotIn("second-token", exported)
            app.toggle[0].set_value(True).run()
            app.chat_input[0].set_value("When does that start?").run()
            self.assertEqual(request.call_args.kwargs["json"]["previous_turn"]["answer"], "Thirty days [1].")
            self.assertEqual(len(app.chat_message), 4)
            self.assertFalse(app.toggle[0].value)
            app.selectbox[0].select("first").run()
            self.assertEqual(len(app.chat_message), 0)
            self.assertFalse(app.get("download_button"))
            response.json.return_value = {"answer": "Lecture notes.", "citations": []}
            app.chat_input[0].set_value("What is this?").run()
            self.assertNotIn("previous_turn", request.call_args.kwargs["json"])
            self.assertEqual(request.call_args.kwargs["headers"]["Authorization"], "Bearer first-token")
            self.assertNotIn("Full source text", download.call_args.args[1])
            app.selectbox[0].select("second").run()
            self.assertEqual(len(app.chat_message), 4)
            self.assertFalse(app.exception)

    def test_passage_search_uses_active_document_and_leaves_chat_alone(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[2] / "ui" / "streamlit_app.py")).run()
        app.session_state["documents"] = {"http://localhost:8000": {
            "first": {"name": "first.txt", "token": "first-token"},
            "second": {"name": "second.txt", "token": "second-token"},
        }}
        app.run()
        app.radio[0].set_value("Find passages").run()
        app.radio[1].set_value("Exact phrase")
        next(w for w in app.text_input if w.label == "Search this document").input("INV-1042")
        response = Mock()
        response.json.return_value = {"passages": [
            {"source_name": "second.txt", "page": None, "passage": "Payment for INV-1042"}
        ]}
        with patch("requests.post", return_value=response) as request:
            next(w for w in app.button if w.label == "Find passages").click().run()
            self.assertTrue(request.call_args.args[0].endswith("/search"))
            self.assertEqual(request.call_args.kwargs["json"], {"doc_id": "second", "query": "INV-1042", "mode": "exact"})
            self.assertEqual(request.call_args.kwargs["headers"]["Authorization"], "Bearer second-token")
            self.assertTrue(any("Payment for INV-1042" in w.value for w in app.markdown))
            app.selectbox[0].select("first").run()
            self.assertFalse(any("INV-1042" in w.value for w in app.markdown))
            app.selectbox[0].select("second").run()
            app.radio[0].set_value("Chat").run()
            self.assertFalse(app.chat_message)
            self.assertEqual(request.call_count, 1)
        self.assertFalse(app.exception)

    def test_notebook_collects_sources_notes_and_exports_by_document(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[2] / "ui" / "streamlit_app.py")).run()
        source = {"source_name": "paper.pdf", "page": 2, "chunk_id": "p2c1", "passage": "The library closes at eight."}
        app.session_state["documents"] = {"http://localhost:8000": {
            "other": {"name": "paper.pdf", "token": "other-token"},
            "active": {
                "name": "paper.pdf", "token": "private-token",
                "turns": [{"question": "When?", "answer": "Eight [1].", "citations": [source]}],
                "search": {"query": "hours", "mode": "Hybrid", "passages": [source]},
            },
        }}
        def button(label):
            return next(b for b in app.button if b.label == label)

        app.run()
        button("Save passage").click().run()
        app.radio[0].set_value("Find passages").run()
        self.assertTrue(button("Saved to notebook").disabled)
        app.radio[0].set_value("Notebook").run()
        self.assertEqual(len(app.text_area), 1)
        app.text_area[0].input("Confirm Friday hours.")
        with patch.object(st, "download_button", wraps=st.download_button) as download:
            button("Save note").click().run()
            exported = download.call_args.args[1]
            for expected in ("paper.pdf · Page 2", source["passage"], "Confirm Friday hours."):
                self.assertIn(expected, exported)
            self.assertNotIn("private-token", exported)
        app.selectbox[0].select("other").run()
        self.assertFalse(app.text_area)
        self.assertFalse(app.get("download_button"))
        app.selectbox[0].select("active").run()
        self.assertEqual(app.text_area[0].value, "Confirm Friday hours.")
        button("Remove from notebook").click().run()
        self.assertFalse(app.text_area)
        app.radio[0].set_value("Find passages").run()
        button("Save passage").click().run()
        app.radio[0].set_value("Notebook").run()
        self.assertEqual(app.text_area[0].value, "")
        self.assertFalse(app.exception)
