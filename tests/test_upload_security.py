"""Failure-path tests for private file operations."""
import tempfile
import unittest
from unittest.mock import patch
from security.auth import AuthStore
from security.workspace import Workspace
from security.uploads import save_upload
from security.parser import parse_private_document

class UploadFailureTests(unittest.TestCase):
    def test_failed_parser_preserves_previous_document(self):
        with tempfile.TemporaryDirectory() as root:
            store=AuthStore(root);store.register('upload_test','a long upload test password','test')
            workspace=Workspace(store,store.login('upload_test','a long upload test password','test'))
            path=workspace.upload_path('same.txt');path.write_bytes(b'original secret')
            with patch('ingestion.pipeline.ingest_upload',side_effect=ValueError('parser failure')):
                with self.assertRaises(ValueError):save_upload(workspace,'same.txt',b'replacement')
                self.assertEqual(path.read_bytes(),b'original secret')
                with self.assertRaises(ValueError):save_upload(workspace,'new.txt',b'replacement')
                self.assertFalse(workspace.upload_path('new.txt').exists())
    def test_parser_process_handles_text_and_rejects_invalid_document(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root)/'uploads';folder.mkdir()
            path=folder/'test.txt';path.write_text('Private parser test text.',encoding='utf-8')
            docs=parse_private_document(path)
            self.assertEqual(docs[0].page_content,'Private parser test text.')
            bad=folder/'bad.pdf';bad.write_bytes(b'%PDF-not-a-document')
            with self.assertRaises(ValueError):parse_private_document(bad)

if __name__=='__main__':unittest.main()
