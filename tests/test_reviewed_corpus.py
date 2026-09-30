import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from langchain_core.documents import Document
from ingestion.pipeline import parse_source
from rag.retriever import route_regimes

class ReviewedCorpusTests(unittest.TestCase):
    def test_english_boundary_preserves_original_page_citation(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();(root/'source.pdf').write_bytes(b'%PDF-fixture')
            source={'source_id':'fixture','local_file_path':'source.pdf','page_start':1,'first_page_marker':'MINISTRY','required_patterns':['English rule']}
            docs=[Document(page_content='unreadable legacy font '*10,metadata={'page':0}),Document(page_content='legacy prefix MINISTRY English rule with enough readable authority text for this fixture.',metadata={'page':1})]
            with patch('ingestion.pipeline.BASE_DIR',root),patch('ingestion.pipeline.load_document',return_value=docs):
                chunks,_=parse_source(source)
            self.assertEqual(len(chunks),1)
            self.assertTrue(chunks[0].page_content.startswith('MINISTRY'))
            self.assertEqual(chunks[0].metadata['page'],1)
            self.assertNotIn('legacy',chunks[0].page_content)

    def test_changed_pdf_boundary_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();(root/'source.pdf').write_bytes(b'%PDF-fixture')
            source={'source_id':'fixture','local_file_path':'source.pdf','page_start':0,'first_page_marker':'MISSING'}
            with patch('ingestion.pipeline.BASE_DIR',root),patch('ingestion.pipeline.load_document',return_value=[Document(page_content='Different document')]):
                with self.assertRaisesRegex(ValueError,'marker missing'):parse_source(source)

    def test_new_source_routes(self):
        self.assertIn('export_uk',route_regimes('UK MHRA THR registration'))
        self.assertIn('privacy',route_regimes('DPDP personal data consent'))
        self.assertIn('ai_governance',route_regimes('NIST AI RMF'))

if __name__=='__main__':unittest.main()
