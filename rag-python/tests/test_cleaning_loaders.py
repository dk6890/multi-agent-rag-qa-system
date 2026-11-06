import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cleaning import clean_text
from document_loader import load_document


class CleaningTests(unittest.TestCase):
    def test_normalizes_bom_line_endings_and_spaces(self):
        self.assertEqual(clean_text('\ufeff  甲\u3000\t乙\r\n\r\n\r\n丙  '), '甲 乙\n\n丙')

    def test_short_valid_text_is_not_removed(self):
        for text in ['是', '否。', '第一条', 'Q: OK?\nA: Yes.', '金额：0元', '1']:
            with self.subTest(text=text):
                self.assertEqual(clean_text(text), text)

    def test_idempotent_without_losing_content(self):
        text = '第一章 合同\n\n问：如何续签？\n答：到期前办理。\n1 + 1 = 2'
        self.assertEqual(clean_text(text), text)
        self.assertEqual(clean_text(clean_text(text)), clean_text(text))


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='rag-loader-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_txt_encodings_preserve_every_character(self):
        text = '第一章\n问题：怎样申请？\n答案：提交材料。'
        for encoding in ['utf-8', 'utf-8-sig', 'utf-16', 'utf-16-le', 'utf-16-be', 'gb18030']:
            with self.subTest(encoding=encoding):
                path = self.root / (encoding + '.txt')
                path.write_bytes(text.encode(encoding))
                pages = load_document(str(path))
                self.assertEqual(clean_text('\n'.join(page['text'] for page in pages)), text)

    def test_gb18030_character_outside_gbk_is_not_silently_dropped(self):
        text = '起始𠀀结束'
        path = self.root / 'extended.txt'
        path.write_bytes(text.encode('gb18030'))
        self.assertEqual(load_document(str(path))[0]['text'], text)

    def test_invalid_bytes_are_rejected_instead_of_ignored(self):
        path = self.root / 'invalid.txt'
        path.write_bytes(b'valid\x81')
        with self.assertRaises((UnicodeError, ValueError)):
            load_document(str(path))

    def test_docx_preserves_paragraph_table_paragraph_order(self):
        from docx import Document

        path = self.root / 'ordered.docx'
        document = Document()
        document.add_paragraph('标题及表格前正文')
        table = document.add_table(rows=2, cols=2)
        for row, values in zip(table.rows, [('参数', '数值'), ('温度', '37度')]):
            for cell, value in zip(row.cells, values):
                cell.text = value
        document.add_paragraph('表格后结论')
        document.save(str(path))
        text = '\n'.join(page['text'] for page in load_document(str(path)))
        terms = ['标题及表格前正文', '参数', '数值', '温度', '37度', '表格后结论']
        positions = [text.index(term) for term in terms]
        self.assertEqual(positions, sorted(positions))

    def pdf_pages(self, texts):
        path = self.root / 'fixture.pdf'
        path.touch()
        class Page:
            height, width, bbox = 800, 600, (0, 0, 600, 800)

            def __init__(self, text):
                self.text = text

            def find_tables(self):
                return []

            def crop(self, bounds):
                is_margin = bounds[3] - bounds[1] <= 45
                return SimpleNamespace(extract_text=lambda: '' if is_margin else self.text)

        pdf = SimpleNamespace(pages=[Page(text) for text in texts])
        manager = unittest.mock.MagicMock()
        manager.__enter__.return_value = pdf
        with patch('pdfplumber.open', return_value=manager):
            return load_document(str(path))

    def test_pdf_page_numbers_keep_empty_page_position(self):
        pages = self.pdf_pages(['首段', '', '尾段'])
        present = [(page['text'], page['metadata']['page']) for page in pages if page['text']]
        self.assertEqual(present, [('首段', 1), ('尾段', 3)])

    def test_pdf_repeated_normal_short_body_is_not_deleted(self):
        pages = self.pdf_pages(['是\n正常正文\n否'] * 3)
        for page in pages:
            self.assertIn('是', page['text'])
            self.assertIn('正常正文', page['text'])
            self.assertIn('否', page['text'])

    def test_missing_and_unsupported_files_fail(self):
        with self.assertRaises(FileNotFoundError):
            load_document(str(self.root / 'missing.txt'))
        path = self.root / 'unsupported.exe'
        path.touch()
        with self.assertRaises(ValueError):
            load_document(str(path))


if __name__ == '__main__':
    unittest.main()
