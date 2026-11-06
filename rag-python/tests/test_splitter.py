import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import splitter.text_splitter as splitter_module
from splitter import split_text


class SplitterTests(unittest.TestCase):
    def split_document(self, text, limit=80, **kwargs):
        splitter = getattr(splitter_module, 'split_document', None)
        self.assertTrue(callable(splitter), 'upgrade must export split_document')
        pages = text if isinstance(text, list) else [{'text': text, 'metadata': {'page': 3, 'sourceType': 'pdf'}}]
        chunks = splitter(pages, token_counter=len, max_tokens=limit, file_name='fixture.txt', **kwargs)
        for chunk in chunks:
            self.assertTrue(chunk['text'].strip())
            self.assertLessEqual(len(chunk['text']), limit, repr(chunk['text']))
            self.assertIsInstance(chunk['metadata'], dict)
        self.assertEqual([chunk['chunkIndex'] for chunk in chunks], list(range(1, len(chunks) + 1)))
        return chunks

    def test_legacy_split_text_interface(self):
        self.assertEqual(split_text('', chunk_size=8, overlap=2), [])
        self.assertEqual(split_text('短文', chunk_size=8, overlap=2), ['短文'])
        source = 'abcdefghijklmnopqrstuv'
        chunks = split_text(source, chunk_size=8, overlap=2)
        self.assertTrue(all(len(chunk) <= 8 for chunk in chunks))
        self.assertTrue(all(character in ''.join(chunks) for character in source))

    def test_short_body_and_metadata_survive(self):
        chunks = self.split_document('正常短文。')
        self.assertEqual(chunks[0]['text'], '正常短文。')
        self.assertEqual(chunks[0]['metadata']['page'], 3)

    def test_heading_and_body_count_together_toward_limit(self):
        chunks = self.split_document('# 服务申请\n' + '办理条件及说明。' * 35, limit=40)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertIn('服务申请', chunk['text'])

    def test_oversized_heading_and_question_do_not_overflow_or_lose_tail(self):
        text = '# ' + '长标题' * 45 + '\n问：' + '如何办理' * 45 + '？\n答：' + '办理说明' * 80 + '。结束标记'
        chunks = self.split_document(text, limit=32)
        self.assertGreater(len(chunks), 1)
        self.assertIn('结束标记', ''.join(chunk['text'] for chunk in chunks))

    def test_long_question_answer_keeps_question_context(self):
        chunks = self.split_document('问：如何申请？\n答：' + '提交材料并审核。' * 40, limit=48)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertIn('如何申请', chunk['text'])

    def test_no_nonwhitespace_character_is_swallowed_at_boundaries(self):
        source = ''.join(chr(0x4E00 + index) for index in range(280))
        text = ''.join(chunk['text'] for chunk in self.split_document(source, limit=23))
        cursor = iter(re.sub(r'\s+', '', text))
        self.assertTrue(all(any(candidate == character for candidate in cursor) for character in source))

    def test_multipage_metadata_is_not_reassigned(self):
        pages = [{'text': '第一页内容', 'metadata': {'page': 1}}, {'text': '第三页内容', 'metadata': {'page': 3}}]
        chunks = self.split_document(pages)
        for phrase, page in [('第一页内容', 1), ('第三页内容', 3)]:
            chunk = next(chunk for chunk in chunks if phrase in chunk['text'])
            self.assertEqual(chunk['metadata']['page'], page)

    def test_empty_document_is_empty(self):
        self.assertEqual(self.split_document(' \n\t '), [])

    def test_nontrivial_counter_not_character_count_controls_budget(self):
        splitter = getattr(splitter_module, 'split_document', None)
        self.assertTrue(callable(splitter))
        counter = lambda text: len(text.encode('utf-8'))
        chunks = splitter([{'text': '# 标题\n' + '中文内容。' * 45, 'metadata': {}}], token_counter=counter, max_tokens=60)
        self.assertTrue(chunks)
        self.assertTrue(all(counter(chunk['text']) <= 60 for chunk in chunks))


if __name__ == '__main__':
    unittest.main()
