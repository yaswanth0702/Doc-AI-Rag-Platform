import io
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import numpy as np
import requests
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app import main
from app.rag import generator


class DocumentTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.uploads = Path(temp.name) / "uploads"
        self.index = Path(temp.name) / "index"
        settings = replace(
            main.settings, uploads_dir=str(self.uploads), index_dir=str(self.index),
            gemini_api_key="test-only",
        )
        self.enterContext(patch.object(main, "settings", settings))
        self.enterContext(patch.object(generator, "settings", settings))
        embedder = Mock()
        embedder.embed_texts.side_effect = lambda texts: np.ones((len(texts), 1), dtype="float32")
        embedder.embed_query.return_value = np.ones(1, dtype="float32")
        self.enterContext(patch.object(main, "get_embedder", return_value=embedder))
        self.provider = self.enterContext(patch.object(generator.requests, "post"))
        self.provider.return_value.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "From the document [1]."}]}}]
        }
        self.client = self.enterContext(TestClient(main.app))

    def upload(self, text=b"original text", name="notes.txt"):
        response = self.client.post("/ingest", files={"file": (name, text)})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def ask(self, doc, token=None):
        return self.client.post(
            "/ask", json={"question": "What does it say?", "doc_id": doc["doc_id"]},
            headers={"Authorization": "Bearer " + (token or doc["document_token"])},
        )

    def test_same_filename_versions_retrieve_only_the_selected_text(self):
        first = self.upload()
        second = self.upload(b"updated text")
        self.assertNotEqual(first["doc_id"], second["doc_id"])
        self.assertEqual({p.read_bytes() for p in self.uploads.iterdir()}, {b"original text", b"updated text"})
        for doc, expected in [(first, "original text"), (second, "updated text")]:
            result = self.ask(doc)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()["citations"][0]["snippet"], expected)
            self.assertEqual(result.json()["citations"][0]["source_name"], "notes.txt")
            self.assertEqual(result.json()["answer"], "From the document [1].")

    def test_access_is_document_specific(self):
        first = self.upload()
        second = self.upload(b"second")
        self.assertEqual(self.ask(first, second["document_token"]).status_code, 404)
        response = self.client.post("/ask", json={"doc_id": first["doc_id"], "question": "Summary?"})
        self.assertEqual(response.status_code, 401)
        self.provider.assert_not_called()

    def test_no_selection_or_no_hits_skips_generation(self):
        result = self.client.post("/ask", json={"question": "What does it say?"})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["citations"], [])
        doc = self.upload()
        with patch.object(main.Retriever, "retrieve", return_value=[]):
            self.assertEqual(self.ask(doc).json()["citations"], [])
        self.provider.assert_not_called()

    def test_bad_uploads_leave_no_data(self):
        for name, content in [("bad.pdf", b"incomplete PDF"), ("empty.txt", b" ")]:
            response = self.client.post("/ingest", files={"file": (name, content)})
            self.assertEqual(response.status_code, 400)
            self.assertEqual(list(self.uploads.iterdir()), [])
            self.assertEqual(list(self.index.iterdir()), [])

    def test_index_failure_rolls_back_files(self):
        with patch.object(main.FaissStore, "add", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.upload()
        self.assertEqual(list(self.uploads.iterdir()), [])
        self.assertEqual(list(self.index.iterdir()), [])

    def test_missing_key_and_provider_errors_are_service_errors(self):
        doc = self.upload()
        with patch.object(generator, "settings", replace(generator.settings, gemini_api_key="")):
            self.assertEqual(self.ask(doc).status_code, 503)
            self.provider.assert_not_called()
        self.provider.side_effect = requests.Timeout()
        self.assertEqual(self.ask(doc).status_code, 503)
        self.provider.side_effect = None
        self.provider.return_value.json.return_value = {"candidates": []}
        self.assertEqual(self.ask(doc).status_code, 503)

    def test_pdf_passage_retains_page_number(self):
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        page = writer.add_blank_page(width=200, height=200)
        font = DictionaryObject({
            NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        })
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})
        })
        stream = DecodedStreamObject()
        stream.set_data(b"BT /F1 10 Tf 10 40 Td (Sample passage) Tj ET")
        page[NameObject("/Contents")] = stream
        pdf = io.BytesIO()
        writer.write(pdf)
        result = self.ask(self.upload(pdf.getvalue(), "paper.pdf"))
        self.assertEqual(result.json()["citations"][0]["page"], 2)
        self.assertEqual(result.json()["citations"][0]["snippet"], "Sample passage")

    def test_follow_up_retrieves_with_previous_turn_and_returns_full_passage(self):
        text = "The invoice is due in thirty days. " * 12
        doc = self.upload(text.encode())
        previous = {"question": "What is the payment deadline?", "answer": "Thirty days."}
        with patch.object(main.Retriever, "retrieve", autospec=True, side_effect=main.Retriever.retrieve) as retrieve:
            response = self.client.post(
                "/ask", json={"doc_id": doc["doc_id"], "question": "When does it start?", "previous_turn": previous},
                headers={"Authorization": "Bearer " + doc["document_token"]},
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn(previous["question"], retrieve.call_args.args[1])
        self.assertIn(previous["answer"], retrieve.call_args.args[1])
        prompt = self.provider.call_args.kwargs["json"]["contents"][0]["parts"][0]["text"]
        self.assertIn(previous["answer"], prompt)
        citation = response.json()["citations"][0]
        self.assertEqual(citation["passage"], text.strip())
        self.assertLess(len(citation["snippet"]), len(citation["passage"]))

    def test_history_length_is_validated(self):
        doc = self.upload()
        response = self.client.post(
            "/ask", json={"doc_id": doc["doc_id"], "question": "Explain?",
                          "previous_turn": {"question": "old", "answer": "x" * 1201}},
            headers={"Authorization": "Bearer " + doc["document_token"]},
        )
        self.assertEqual(response.status_code, 422)
        self.provider.assert_not_called()

    def search(self, doc, query, mode="hybrid", token=None, limit=6):
        return self.client.post(
            "/search", json={"doc_id": doc["doc_id"], "query": query, "mode": mode, "limit": limit},
            headers={"Authorization": "Bearer " + (token or doc["document_token"])},
        )

    def test_exact_search_works_without_embedding_or_generation(self):
        doc = self.upload(b"Terms: INV-1042 is payable within thirty\n days.")
        with patch.object(main, "get_embedder", side_effect=AssertionError("unexpected embedding")):
            response = self.search(doc, "THIRTY days", "exact")
            self.assertEqual(response.status_code, 200)
            self.assertIn("INV-1042", response.json()["passages"][0]["passage"])
            self.assertEqual(self.search(doc, "INV-9999", "exact").json()["passages"], [])
        self.provider.assert_not_called()

    def test_search_access_limits_and_empty_queries(self):
        first, second = self.upload(), self.upload()
        for mode in ("exact", "hybrid"):
            self.assertEqual(self.search(first, "notes", mode, second["document_token"]).status_code, 404)
        self.assertEqual(self.search(first, "  ").status_code, 422)
        self.assertEqual(self.search(first, "notes", limit=21).status_code, 422)
        self.provider.assert_not_called()

    def test_hybrid_prioritizes_matching_code_and_ask_uses_same_source(self):
        # With tied mock vectors FAISS alone puts the final chunk first.
        data = "INV-1042 is payable in thirty days. " + "ordinary text " * 170
        doc = self.upload(data.encode())
        response = self.search(doc, "INV-1042", limit=1)
        self.assertEqual(response.status_code, 200)
        passages = response.json()["passages"]
        self.assertEqual(len(passages), 1)
        self.assertIn("INV-1042", passages[0]["passage"])
        self.provider.assert_not_called()
        answer = self.client.post(
            "/ask", json={"doc_id": doc["doc_id"], "question": "INV-1042"},
            headers={"Authorization": "Bearer " + doc["document_token"]},
        )
        self.assertEqual(answer.json()["citations"][0]["chunk_id"], passages[0]["chunk_id"])

    def test_gemini_errors_show_safe_specific_guidance(self):
        doc = self.upload()
        cases = [
            (400, "API_KEY_INVALID", "valid GEMINI_API_KEY"),
            (400, "OTHER_REASON", "request configuration"),
            (403, "", "Access denied"),
            (404, "", "GEMINI_MODEL"),
            (429, "", "quota"),
            (503, "", "server error"),
        ]
        for status, reason, expected in cases:
            with self.subTest(status=status, reason=reason):
                upstream = requests.Response()
                upstream.status_code = status
                upstream.json = Mock(return_value={"error": {
                    "message": "private upstream detail",
                    "details": [{"reason": reason}],
                }})
                self.provider.return_value = upstream
                response = self.ask(doc)
                self.assertEqual(response.status_code, 503)
                detail = response.json()["detail"]
                self.assertIn(f"Gemini API returned HTTP {status}", detail)
                self.assertIn(expected, detail)
                self.assertNotIn("private upstream detail", detail)

    def test_gemini_transport_errors_are_distinguishable(self):
        doc = self.upload()
        for exc, expected in [(requests.Timeout(), "timed out"), (requests.ConnectionError(), "internet connection")]:
            self.provider.side_effect = exc
            response = self.ask(doc)
            self.assertEqual(response.status_code, 503)
            self.assertIn(expected, response.json()["detail"])
