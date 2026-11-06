import codecs
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from cleaning import clean_text
from config import settings
from document_loader import load_document
from document_loader.loaders import _table_rows
from embedding import EmbeddingUnavailableError
from retrieval.service import RagService, _merge_references
from splitter import split_document, split_text
from vector_store import ChromaVectorStore


class CleaningAndLoaderTests(unittest.TestCase):
    def test_cleaning_preserves_meaning_and_paragraphs(self):
        raw = "\ufeffsun\u8001\u5e08\r\n\r\n\u8d39\u7528: 123.45\u5143; -5%; C++\u3002\u200b"
        cleaned = clean_text(raw)
        self.assertEqual(cleaned, "sun\u8001\u5e08\n\n\u8d39\u7528: 123.45\u5143; -5%; C++\u3002")
        self.assertEqual(clean_text(cleaned), cleaned)

    def test_txt_encodings_are_lossless(self):
        text = "sun\u8001\u5e08\u6559\u96c5\u601d\uff0c\U00020000\u662f\u751f\u50fb\u5b57\u3002"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.txt"
            for encoding in ("utf-8-sig", "utf-16", "utf-32", "gb18030"):
                with self.subTest(encoding=encoding):
                    path.write_bytes(text.encode(encoding))
                    self.assertEqual(load_document(str(path))[0]["text"], text)

    def test_binary_txt_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "binary.txt"
            path.write_bytes(b"hello\x00world")
            with self.assertRaises(ValueError):
                load_document(str(path))

    def test_docx_table_and_title_order(self):
        from docx import Document

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "course.docx"
            document = Document()
            document.add_heading("sun teacher", level=1)
            document.add_paragraph("before table")
            table = document.add_table(rows=2, cols=2)
            table.cell(0, 0).text = "Course"
            table.cell(0, 1).text = "Price"
            table.cell(1, 0).text = "IELTS"
            table.cell(1, 1).text = "0"
            document.add_paragraph("after table")
            document.save(path)
            blocks = load_document(str(path))
            self.assertEqual(len(blocks), 3)
            self.assertEqual(blocks[0]["text"], "before table")
            self.assertIn("Course: IELTS; Price: 0", blocks[1]["text"])
            self.assertEqual(blocks[2]["text"], "after table")
            self.assertTrue(all(block["metadata"]["titlePath"] == "sun teacher" for block in blocks))

    def test_table_zero_is_content(self):
        self.assertIn("Count: 0", _table_rows([["Count"], [0]]))

    def test_scanned_pdf_reports_ocr_requirement(self):
        page = MagicMock()
        page.height, page.width, page.bbox = 100, 100, (0, 0, 100, 100)
        page.crop.return_value.extract_text.return_value = ""
        page.find_tables.return_value = []
        pdf = MagicMock()
        pdf.__enter__.return_value.pages = [page]
        with tempfile.TemporaryDirectory() as folder, patch("pdfplumber.open", return_value=pdf):
            path = Path(folder) / "scan.pdf"
            path.touch()
            with self.assertRaisesRegex(ValueError, "OCR"):
                load_document(str(path))


class SplitterTests(unittest.TestCase):
    def test_split_text_checks_zero_and_overlap(self):
        for size, overlap in ((0, 0), (10, 10), (10, -1)):
            with self.subTest(size=size, overlap=overlap), self.assertRaises(ValueError):
                split_text("abc", chunk_size=size, overlap=overlap)

    def test_title_and_sentence_boundaries(self):
        body = "One complete sentence. " * 30
        chunks = split_document([{"text": "# sun teacher\n## IELTS\n" + body}], file_name="course.txt", max_tokens=120)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all("sun teacher" in chunk["metadata"]["titlePath"] for chunk in chunks))
        self.assertTrue(all(len(chunk["text"]) <= 120 for chunk in chunks))
        self.assertTrue(all("IELTS" in chunk["text"] for chunk in chunks))

    def test_qa_pairs_do_not_mix_answers(self):
        text = "Q: Teacher?\nA: sun\nQ: Course?\nA: IELTS"
        chunks = split_document([{"text": text}], max_tokens=100)
        self.assertEqual(len(chunks), 2)
        self.assertIn("Teacher?", chunks[0]["text"])
        self.assertNotIn("IELTS", chunks[0]["text"])
        self.assertIn("Course?", chunks[1]["text"])

    def test_long_answer_repeats_question_with_token_limit(self):
        count = lambda text: len(text) + 2
        chunks = split_document([{"text": "Q: Course?\nA: " + "writing practice. " * 80}],
                                token_counter=count, max_tokens=80, file_name="sun.txt")
        self.assertGreater(len(chunks), 5)
        self.assertTrue(all("Q: Course?" in chunk["text"] for chunk in chunks))
        self.assertTrue(all(count(chunk["text"]) <= 80 for chunk in chunks))

    def test_empty_and_long_unbroken_text(self):
        self.assertEqual(split_document([{"text": "   "}]), [])
        source = "\u7532" * 400
        chunks = split_document([{"text": source}], max_tokens=80)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk["text"]) <= 80 for chunk in chunks))

    def test_pdf_heading_context_continues_on_next_page(self):
        chunks = split_document([
            {"text": "# sun teacher\nIELTS reading", "metadata": {"sourceType": "pdf", "page": 1}},
            {"text": "writing methods", "metadata": {"sourceType": "pdf", "page": 2}},
        ], max_tokens=80)
        self.assertIn("sun teacher", chunks[-1]["text"])
        self.assertEqual(chunks[-1]["metadata"]["page"], 2)

    def test_plain_course_title_is_retained_in_long_notes(self):
        chunks = split_document([{"text": "sun\u8001\u5e08\u6559\u96c5\u601d\n" + "\u9605\u8bfb\u548c\u5199\u4f5c\u6280\u5de7\u3002" * 40,
                                  "metadata": {"sourceType": "txt"}}], max_tokens=60)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all("sun\u8001\u5e08\u6559\u96c5\u601d" in chunk["text"] for chunk in chunks))


class FusionAndFailureTests(unittest.TestCase):
    @staticmethod
    def reference(chunk_id, text="body"):
        return {"fileId": 1, "fileName": "course.txt", "chunkId": chunk_id, "chunkText": text, "score": 0.9, "metadata": {}}

    def test_vector_only_candidate_is_not_starved(self):
        keywords = [self.reference(f"keyword-{i}") for i in range(20)]
        vector = [self.reference("vector-only")]
        merged = _merge_references(keywords, vector, 5)
        self.assertIn("vector-only", [ref["chunkId"] for ref in merged])

    def test_shared_candidate_is_fused_once(self):
        refs = [self.reference("shared"), self.reference("only-keyword")]
        merged = _merge_references(refs, [self.reference("shared")], 5)
        self.assertEqual(merged[0]["chunkId"], "shared")
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["metadata"]["bm25Rank"], 1)
        self.assertEqual(merged[0]["metadata"]["vectorRank"], 1)
        self.assertTrue(all(0 <= ref["score"] <= 1 for ref in merged))

    def test_embedding_failure_cannot_write_index(self):
        service = RagService()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.txt"
            path.write_text("test course", encoding="utf-8")
            with patch("retrieval.service.EmbeddingProvider", side_effect=EmbeddingUnavailableError("not ready")), \
                    patch("retrieval.service.ChromaVectorStore") as store:
                with self.assertRaises(EmbeddingUnavailableError):
                    service.index_file(file_id=1, file_path=str(path), file_name=path.name)
                store.assert_not_called()

    def test_embedding_failure_is_explicit_lexical_fallback(self):
        service = RagService()
        with patch("retrieval.service.EmbeddingProvider", side_effect=EmbeddingUnavailableError("not ready")), \
                patch("retrieval.service.ChromaVectorStore") as store:
            store.return_value.keyword_search.return_value = [self.reference("legacy")]
            result = service.search(question="sun course", top_k=5)
            self.assertTrue(result[0].metadata["degraded"])
            self.assertEqual(result[0].metadata["searchMode"], "lexical-only")
            store.return_value.search.assert_not_called()


class PersistentIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.path_patch = patch.object(settings, "vector_store_path", cls.folder.name)
        cls.path_patch.start()

    @classmethod
    def tearDownClass(cls):
        cls.path_patch.stop()
        cls.folder.cleanup()

    def setUp(self):
        fingerprint = self.id().split(".")[-1]
        self.store = ChromaVectorStore(fingerprint)

    def write(self, file_id, words):
        return self.store.upsert_chunks(file_id=file_id, file_name=f"{file_id}.txt",
            chunks=[{"chunkIndex": i + 1, "text": text, "metadata": {}} for i, text in enumerate(words)],
            embeddings=[[1.0, 0.0] for _ in words])

    def test_empty_collection_and_large_topk(self):
        self.assertEqual(self.store.search(query_embedding=[1.0, 0.0], top_k=50), [])
        self.write(1, ["sun IELTS"])
        self.assertEqual(len(self.store.search(query_embedding=[1.0, 0.0], top_k=50)), 1)

    def test_reindex_removes_old_tail_but_not_other_files(self):
        self.write(1, ["sun old one", "sun old two", "sun old three"])
        self.write(2, ["moon independent"])
        self.write(1, ["sun replacement"])
        self.assertEqual(self.store.diagnostics()["chunkCount"], 2)
        results = self.store.keyword_search(query="sun", top_k=20)
        self.assertEqual([ref["chunkText"] for ref in results], ["sun replacement"])
        self.assertEqual(len(self.store.keyword_search(query="moon", top_k=5)), 1)

    def test_failed_publication_preserves_old_generation(self):
        self.write(1, ["sun original"])
        from chromadb.api.models.Collection import Collection

        with patch.object(Collection, "modify", side_effect=RuntimeError("simulated failure")):
            with self.assertRaisesRegex(RuntimeError, "simulated"):
                self.write(1, ["sun new"])
        result = self.store.keyword_search(query="sun", top_k=5)
        self.assertEqual([ref["chunkText"] for ref in result], ["sun original"])
        self.assertEqual(self.store.diagnostics()["chunkCount"], 1)

    def test_chinese_bm25_and_cache_invalidation(self):
        self.write(1, ["sun\u8001\u5e08\u8bb2\u6388\u96c5\u601d\u5199\u4f5c", "\u7535\u8111\u7ef4\u4fee\u8bf4\u660e"])
        results = self.store.keyword_search(query="\u6211\u60f3\u5b66\u4e00\u4e0bsun\u6559\u7684\u5185\u5bb9", top_k=5)
        self.assertIn("sun", results[0]["chunkText"])
        self.write(1, ["moon\u8001\u5e08\u8bb2\u6388\u5199\u4f5c"])
        self.assertEqual(self.store.keyword_search(query="sun", top_k=5), [])

    def test_legacy_vectors_cannot_be_searched_semantically(self):
        with self.assertRaisesRegex(ValueError, "Legacy"):
            ChromaVectorStore().search(query_embedding=[1.0, 0.0], top_k=5)

    def test_model_fingerprints_isolate_semantic_vectors(self):
        self.write(1, ["sun first-model"])
        other = ChromaVectorStore("unrelated-test-model")
        self.assertEqual(other.search(query_embedding=[1.0, 0.0], top_k=5), [])
        self.assertEqual(self.store.diagnostics()["chunkCount"], 1)


class ApiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        import app

        cls.app_module = app
        cls.client = TestClient(app.app)

    def test_health_never_initializes_embedding_by_default(self):
        service = RagService()
        with patch.object(self.app_module, "rag_service", service), \
                patch("retrieval.service.EmbeddingProvider") as provider:
            response = self.client.get("/health")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["embedding"]["status"], "not_loaded")
            provider.assert_not_called()

    def test_search_response_keeps_java_contract(self):
        from schemas import Reference

        service = MagicMock()
        service.last_search_warning = None
        service.search.return_value = [Reference(fileId=5, fileName="course.txt", chunkText="sun IELTS", score=0.8)]
        with patch.object(self.app_module, "rag_service", service):
            body = self.client.post("/rag/search", json={"question": "sun", "topK": 5}).json()
            self.assertEqual(body["code"], 200)
            self.assertTrue({"fileId", "fileName", "chunkText", "score"}.issubset(body["data"]["references"][0]))

    def test_index_embedding_failure_has_no_success_payload(self):
        service = MagicMock()
        service.index_file.side_effect = EmbeddingUnavailableError("model missing")
        with patch.object(self.app_module, "rag_service", service):
            body = self.client.post("/rag/index", json={"fileId": 1, "filePath": "private/source.txt", "fileName": "source.txt"}).json()
            self.assertEqual(body["code"], 503)
            self.assertNotIn("chunkCount", body["data"])

    def test_validation_rejects_empty_question(self):
        self.assertEqual(self.client.post("/rag/search", json={"question": ""}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
