import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.rag.chunking import chunk_text
from app.rag.ingest import build_chunks_from_file, recover_pdf_spacing


class PassageTests(unittest.TestCase):
    def test_resume_bullets_remain_complete(self):
        lines = ["• Built REST APIs.", "• Tested services.", "• Wrote reports."]
        chunks = chunk_text("\n".join(lines), chunk_size=38, overlap=19)
        self.assertEqual(chunks, ["\n".join(lines[:2]), "\n".join(lines[1:])])
        self.assertEqual(chunk_text("One ends. Next begins. Final part.", 24, 0),
                         ["One ends. Next begins.", "Final part."])

    def test_words_are_preserved_when_a_sentence_exceeds_the_limit(self):
        words = ["Consultancy", "Services", "developed", "applications", "using", "PostgreSQL"]
        chunks = chunk_text(" ".join(words), chunk_size=24, overlap=10)
        self.assertEqual(set(" ".join(chunks).split()), set(words))
        self.assertTrue(all(len(chunk) <= 24 for chunk in chunks))

    def test_long_unbroken_text_and_invalid_parameters(self):
        self.assertEqual(chunk_text("z" * 29, 10, 3), ["z" * 10, "z" * 10, "z" * 9])
        self.assertEqual(chunk_text("  \r\n"), [])
        for size, overlap in ((0, 0), (5, 5), (5, -1)):
            with self.assertRaises(ValueError):
                chunk_text("abc", size, overlap)

    def test_only_matching_layout_text_contributes_spaces(self):
        p = Mock()
        p.extract_text.return_value = "Built   REST APIs\nJava and SQL"
        self.assertEqual(recover_pdf_spacing(p, "BuiltREST APIs\nJava and SQL"),
                         "Built REST APIs\nJava and SQL")
        p.extract_text.return_value = "Java and SQL\nBuilt REST APIs"
        self.assertEqual(recover_pdf_spacing(p, "BuiltREST APIs\nJava and SQL"),
                         "BuiltREST APIs\nJava and SQL")
        p.extract_text.side_effect = ValueError("Layout unavailable")
        self.assertEqual(recover_pdf_spacing(p, "original"), "original")

    def test_pdf_resume_bullets_and_page_numbers_survive_indexing(self):
        writer = PdfWriter()
        font = DictionaryObject({
            NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        })
        for heading in ("Experience", "Projects"):
            page = writer.add_blank_page(width=612, height=792)
            page[NameObject("/Resources")] = DictionaryObject({
                NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})
            })
            text = [f"BT /F1 10 Tf 12 TL 20 760 Td ({heading}) Tj"]
            for i in range(35):
                text.append(f"T* (- Task {i}: Built and tested Spring Boot APIs.) Tj")
            stream = DecodedStreamObject()
            stream.set_data((" ".join(text) + " ET").encode())
            page[NameObject("/Contents")] = stream
        pdf = io.BytesIO()
        writer.write(pdf)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "resume.pdf"
            path.write_bytes(pdf.getvalue())
            chunks = build_chunks_from_file(str(path), path.name, "test-id")
        for number, heading in enumerate(("Experience", "Projects"), 1):
            passages = [chunk["text"] for chunk in chunks if chunk["page"] == number]
            self.assertGreater(len(passages), 1)
            lines = {line for passage in passages for line in passage.splitlines()}
            expected = {f"- Task {i}: Built and tested Spring Boot APIs." for i in range(35)}
            self.assertEqual(lines, expected | {heading})
