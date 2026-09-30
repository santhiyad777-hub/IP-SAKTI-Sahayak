"""Exercise the exact deployment seed installer without touching the live index."""
import json
import tempfile
from pathlib import Path
import chromadb
from config import BASE_DIR
from deployment.start import seed_public

def main():
    root=Path(tempfile.mkdtemp(prefix='ip-sakti-deploy-check-'))
    first=seed_public(root,BASE_DIR/'deploy_assets')
    second=seed_public(root,BASE_DIR/'deploy_assets')
    collection=chromadb.PersistentClient(path=str(first)).get_collection('ip_sakti_v1')
    rows=collection.get(include=['metadatas'])
    result={'idempotent':first==second,'chunks':collection.count(),'sources':len({m['source_id'] for m in rows['metadatas']}),
        'public_only':all(m.get('source_type') in {'official_pdf','official_web'} and not m.get('owner_id') for m in rows['metadatas']),
        'portable_source_paths':all(not Path(m['source']).is_absolute() and (BASE_DIR/m['source']).is_file() for m in rows['metadatas'])}
    Path('evaluation/deployment_seed_results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
    assert result['idempotent'] and result['public_only'] and result['portable_source_paths'] and result['chunks']==6895 and result['sources']==48
if __name__=='__main__':main()
