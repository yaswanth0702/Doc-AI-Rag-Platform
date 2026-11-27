import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

import numpy as np
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from app import main
from app.rag.vector_store import FaissStore


class PageSearchTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        settings = replace(main.settings, index_dir=directory)
        self.enterContext(patch.object(main, "settings", settings))
        self.doc_id = uuid4()
        self.token = "test-token"
        store = FaissStore(str(main.index_path(self.doc_id, self.token)))
        passages = [
            {"doc_id": str(self.doc_id), "chunk_id": str(page), "source_name": "notes.pdf",
             "page": page, "text": f"Review these notes for lesson {page}."}
            for page in (1, 2)
        ]
        # Page 1 outranks page 2 globally; a page-2 result must still survive limit=1.
        store.add(np.array([[1, 0], [0, 1]], dtype="float32"), passages)
        self.embedder = Mock()
        self.embedder.embed_query.return_value = np.array([1, 0], dtype="float32")
        self.enterContext(patch.object(main, "get_embedder", return_value=self.embedder))
        self.client = self.enterContext(TestClient(main.app))

    def search(self, mode, token=None, **options):
        return self.client.post(
            "/search",
            json={"doc_id": str(self.doc_id), "query": "review", "mode": mode, "limit": 1, **options},
            headers={"Authorization": "Bearer " + (token or self.token)},
        )

    def test_both_modes_scope_before_limiting(self):
        for mode in ("hybrid", "exact"):
            with self.subTest(mode=mode):
                self.assertEqual(self.search(mode).json()["passages"][0]["page"], 1)
                result = self.search(mode, page=2)
                self.assertEqual(result.status_code, 200)
                self.assertEqual([item["page"] for item in result.json()["passages"]], [2])
                self.assertEqual(self.search(mode, page=3).json()["passages"], [])

    def test_page_validation_and_access(self):
        for page in (0, -1, 1.5, True):
            self.assertEqual(self.search("hybrid", page=page).status_code, 422)
        self.assertEqual(self.search("exact", token="wrong", page=2).status_code, 404)
        self.embedder.embed_query.assert_not_called()


class PageSearchInterfaceTests(unittest.TestCase):
    def test_page_filter_in_hosted_workspace(self):
        script = Path(__file__).resolve().parents[2] / "ui" / "streamlit_app.py"
        backend = "http://backend.test"
        with patch.dict(os.environ, {"DOCINTEL_BACKEND_URL": backend + "/"}):
            app = AppTest.from_file(str(script)).run()
            self.assertFalse(any(field.label == "Backend URL" for field in app.text_input))
            app.session_state["documents"] = {backend: {
                "text": {"name": "notes.txt", "token": "text-token"},
                "pdf": {"name": "notes.PDF", "token": "pdf-token"},
            }}
            app.run()
            app.radio[0].set_value("Find passages").run()
            app.number_input[0].set_value(2)
            app.text_input[0].set_value("deadline")
            response = Mock()
            response.json.return_value = {"passages": []}
            with patch("requests.post", return_value=response) as request:
                next(b for b in app.button if b.label == "Find passages").click().run()
                self.assertEqual(request.call_args.args[0], backend + "/search")
                self.assertEqual(request.call_args.kwargs["json"]["page"], 2)
                self.assertTrue(any("Page 2" in caption.value for caption in app.caption))
                app.number_input[0].set_value(None)
                next(b for b in app.button if b.label == "Find passages").click().run()
                self.assertNotIn("page", request.call_args.kwargs["json"])
            app.selectbox[0].select("text").run()
            self.assertFalse(app.number_input)
            self.assertFalse(app.exception)
