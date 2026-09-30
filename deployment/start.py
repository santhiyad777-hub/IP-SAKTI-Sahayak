"""Fail-closed production launcher and idempotent public corpus installation."""
import gzip
import hashlib
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit


def seed_public(root,assets):
    import chromadb
    manifest=json.loads((assets/'seed.json').read_text(encoding='utf-8'))
    seed=assets/'corpus.jsonl.gz'
    if hashlib.sha256(seed.read_bytes()).hexdigest()!=manifest['sha256']:raise RuntimeError('Corpus checksum mismatch')
    # Versioned public indexes let an update rebuild without touching private data.
    folder=root/'public_indexes'/manifest['sha256']
    done=folder/'ready.json'
    if not done.exists():
        db=chromadb.PersistentClient(path=str(folder)).get_or_create_collection(manifest['collection'])
        batch=[]
        def upsert(rows):
            db.upsert(ids=[r['id'] for r in rows],documents=[r['document'] for r in rows],metadatas=[r['metadata'] for r in rows],embeddings=[r['embedding'] for r in rows])
        with gzip.open(seed,'rt',encoding='utf-8') as f:
            for line in f:
                batch.append(json.loads(line))
                if len(batch)==128:upsert(batch);batch=[]
        if batch:upsert(batch)
        if db.count()!=manifest['chunks']:raise RuntimeError('Incomplete corpus installation')
        done.write_text(json.dumps(manifest),encoding='utf-8')
    return folder


def main():
    os.umask(0o077)
    url=urlsplit(os.environ.get('PUBLIC_BASE_URL',''))
    if url.scheme!='https' or not url.hostname or url.username or url.path not in ('','/'):
        raise SystemExit('Set PUBLIC_BASE_URL to the HTTPS origin assigned to this service.')
    root=Path(os.environ.get('APP_DATA_DIR','/var/data/ip-sakti')).resolve()
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    probe=root/'.write-check';probe.write_text('ok');probe.unlink()
    base=Path(__file__).resolve().parents[1]
    os.environ['APP_ENV']='production'
    os.environ['APP_DATA_DIR']=str(root)
    os.environ['CHROMA_DB_PATH']=str(seed_public(root,base/'deploy_assets'))
    os.environ['STREAMLIT_BROWSER_SERVER_ADDRESS']=url.hostname
    os.environ['STREAMLIT_BROWSER_SERVER_PORT']=str(url.port or 443)
    port=int(os.environ.get('PORT','8501'))
    if not 1<=port<=65535:raise SystemExit('Invalid PORT')
    os.chdir(base)
    os.execv(sys.executable,[sys.executable,'-m','streamlit','run','app.py','--server.address=0.0.0.0',f'--server.port={port}','--server.headless=true'])

if __name__=='__main__':main()
