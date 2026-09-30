"""Read-only deployment/corpus checks. No API requests and no secret values."""
import hashlib
import json
import platform
import sys
from pathlib import Path
from config import BASE_DIR, OLLAMA_API_KEY, CORPUS_COLLECTION
from utils.bhashini import configured

def main():
    root=BASE_DIR
    manifest=json.loads((root/'dataset/source_registry/curated.json').read_text(encoding='utf-8'))
    checks=[]
    for source in manifest:
        if source.get('status')!='verified': continue
        path=(root/source.get('local_file_path','')).resolve()
        present=path.is_relative_to(root.resolve()) and path.is_file()
        digest=hashlib.sha256(path.read_bytes()).hexdigest() if present else None
        expected=source.get('content_hash')
        checks.append({'source_id':source['source_id'],'present':present,'hash_recorded':bool(expected),'hash_matches':digest==expected if expected else None})
    from vectordb.chroma_manager import load_vector_database
    db=load_vector_database(CORPUS_COLLECTION)
    meta=db.get(include=['metadatas'])['metadatas']
    ids={m.get('source_id') for m in meta}
    active={s['source_id'] for s in manifest if s.get('status')=='verified'}
    report={'python':platform.python_version(),'isolated_environment':sys.prefix!=sys.base_prefix,
        'ollama_key_configured':bool(OLLAMA_API_KEY),'bhashini_configured':configured(),
        'active_sources':len(active),'indexed_sources':len(ids),'chunks':len(meta),
        'unindexed_sources':sorted(active-ids),'unexpected_indexed_sources':sorted(ids-active),
        'source_files':checks,'citation_metadata_complete':all(all(m.get(k) for k in ('source_id','source_url','jurisdiction','content_hash')) for m in meta)}
    report['passed']=bool(meta) and bool(OLLAMA_API_KEY) and not report['unindexed_sources'] and not report['unexpected_indexed_sources'] and report['citation_metadata_complete'] and all(c['present'] and c['hash_matches'] is not False for c in checks)
    (root/'evaluation/readiness_results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='source_files'},indent=2))
    raise SystemExit(0 if report['passed'] else 1)
if __name__=='__main__':main()
