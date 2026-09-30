"""Authenticated upload persistence check with a synthetic private workspace."""
import json
import tempfile
import uuid
from pathlib import Path
from config import BASE_DIR,CORPUS_COLLECTION
from security.auth import AuthStore
from security.workspace import Workspace
from ingestion.pipeline import ingest_upload,write_json
from vectordb.chroma_manager import load_vector_database,load_private_database,delete_document_from_vector_database
from rag.retriever import retrieve_documents

def main():
    root=Path(tempfile.mkdtemp(prefix='ip-sakti-storage-check-'))
    store=AuthStore(root);store.register('storage_test','storage test long passphrase','test')
    space=Workspace(store,store.login('storage_test','storage test long passphrase','test'))
    name='sih-storage-check-'+uuid.uuid4().hex+'.txt';path=space.upload_path(name)
    text='Storage evaluation fixture. The laboratory sample identifier is ZEPHYR. This is synthetic test data, not legal evidence. '
    uploads=load_private_database(space)
    try:
        path.write_text(text*5,encoding='utf-8')
        ingest_upload(path,workspace=space);first=uploads.get(where={'source_id':str(path)})['ids']
        ingest_upload(path,workspace=space);second=uploads.get(where={'source_id':str(path)})['ids']
        docs=retrieve_documents('What is the laboratory sample identifier ZEPHYR?',mode='Uploaded documents',selected_files=[name],workspace=space)
        curated=load_vector_database(CORPUS_COLLECTION).get(include=['metadatas'])
        result={'repeat_ingestion_pass':bool(first) and set(first)==set(second),
            'selected_upload_filter_pass':bool(docs) and all(d.metadata.get('owner_id')==space.owner and Path(d.metadata['source']).name==name for d in docs),
            'curated_chunks':len(curated['ids']),
            'source_metadata_pass':all(all(m.get(k) for k in ['source_id','source_url','jurisdiction','content_hash']) for m in curated['metadatas'])}
    finally:
        delete_document_from_vector_database(path,workspace=space);path.unlink(missing_ok=True)
    result['fixture_cleanup_pass']=len(uploads.get()['ids'])==0 and not path.exists()
    store.logout(space.token,all_sessions=True)
    write_json(BASE_DIR/'evaluation/storage_results.json',result);print(json.dumps(result,indent=2))
    assert all(result[k] for k in ('repeat_ingestion_pass','selected_upload_filter_pass','source_metadata_pass','fixture_cleanup_pass'))
if __name__=='__main__':main()
