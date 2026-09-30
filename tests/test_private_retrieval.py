"""Private vector retrieval uses physically separate stores and owner predicates."""
import hashlib
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from langchain_core.embeddings import Embeddings
from langchain_core.documents import Document
from security.auth import AuthStore,AuthenticationError
from security.workspace import Workspace

class FixedEmbeddings(Embeddings):
    def embed_query(self,text):
        result=[0.0]*384
        for word in text.lower().split():result[int(hashlib.sha256(word.encode()).hexdigest()[:8],16)%384]+=1
        length=math.sqrt(sum(v*v for v in result)) or 1
        return [v/length for v in result]
    def embed_documents(self,texts):return [self.embed_query(t) for t in texts]

class PrivateRetrievalTests(unittest.TestCase):
    def test_two_users_same_filename_no_cross_user_results(self):
        import vectordb.chroma_manager as manager
        from rag.retriever import retrieve_documents
        # Chroma keeps persistent file handles on Windows: fixture lives in OS temp,
        # contains only synthetic text and is not part of the application corpus.
        root=Path(tempfile.mkdtemp(prefix='ip-sakti-vector-security-'))
        store=AuthStore(root)
        spaces=[]
        with patch.object(manager,'get_embedding_model',return_value=FixedEmbeddings()):
            for user,secret in [('alice','ALICE_ONLY_ZEPHYR'),('bob','BOB_ONLY_QUARTZ')]:
                store.register(user,'a very long test passphrase',user)
                space=Workspace(store,store.login(user,'a very long test passphrase',user));spaces.append(space)
                path=space.upload_path('same.txt');content=f'The confidential laboratory identifier is {secret}. Laboratory sample report.'
                path.write_text(content)
                manager.create_or_update_vector_database([Document(page_content=content,metadata={'source':str(path),'source_type':'upload'})],workspace=space)
            for space,own,other in [(spaces[0],'ALICE_ONLY_ZEPHYR','BOB_ONLY_QUARTZ'),(spaces[1],'BOB_ONLY_QUARTZ','ALICE_ONLY_ZEPHYR')]:
                docs=retrieve_documents('What is the confidential laboratory identifier?',mode='Uploaded documents',selected_files=['same.txt'],workspace=space)
                self.assertTrue(docs);self.assertIn(own,str(docs));self.assertNotIn(other,str(docs))
                self.assertTrue(all(d.metadata['owner_id']==space.owner for d in docs))
            with self.assertRaises(PermissionError):retrieve_documents('laboratory identifier',mode='Uploaded documents')
            with self.assertRaises(PermissionError):manager.load_vector_database('langchain')
            with self.assertRaises(PermissionError):manager.create_or_update_vector_database([Document(page_content='private',metadata={'source':'secret.txt'})])
            with self.assertRaises(PermissionError):manager.delete_document_from_vector_database(spaces[0].upload_path('same.txt'),workspace=spaces[1])
            store.logout(spaces[0].token)
            with self.assertRaises(AuthenticationError):retrieve_documents('laboratory identifier',mode='Uploaded documents',workspace=spaces[0])
            manager.delete_document_from_vector_database(spaces[1].upload_path('same.txt'),workspace=spaces[1])
            self.assertEqual(manager.load_private_database(spaces[1]).get()['ids'],[])

if __name__=='__main__':unittest.main()
