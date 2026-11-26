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
