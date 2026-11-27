import unittest
from pathlib import Path
from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest


class SearchDownloadTests(unittest.TestCase):
    def test_export_contains_current_results_and_page_filter(self):
        app_path = Path(__file__).resolve().parents[2] / "ui" / "streamlit_app.py"
        app = AppTest.from_file(str(app_path)).run()
        page = {"source_name": "a.pdf", "page": 2, "passage": "Use small batches.", "chunk_id": "c2"}
        app.session_state["documents"] = {"http://localhost:8000": {
            "other": {"name": "b.pdf", "token": "another-token"},
            "active": {"name": "a.pdf", "token": "document-secret", "search": {
                "query": "batches", "mode": "Exact phrase", "page": 2, "passages": [page],
            }},
        }}
        app.run()
        with patch.object(st, "download_button", wraps=st.download_button) as download:
            app.radio[0].set_value("Find passages").run()
            self.assertFalse(app.exception)
            label, exported = download.call_args.args
            self.assertEqual(label, "Download search results")
            self.assertIn("Search: batches", exported)
            self.assertIn("Exact phrase · Page 2", exported)
            self.assertIn("[1] a.pdf · Page 2", exported)
            self.assertIn("Use small batches.", exported)
            self.assertNotIn("document-secret", exported)
            download.reset_mock()
            app.selectbox[0].select("other").run()
            download.assert_not_called()
