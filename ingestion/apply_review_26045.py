"""Apply the reviewed SIH26045 manifest and synchronize the active corpus."""
import json
import shutil
from collections import Counter
from pathlib import Path
from datetime import datetime, timezone
from config import BASE_DIR, CORPUS_COLLECTION
from ingestion.pipeline import parse_source, ingest_manifest, write_json

REVIEW = BASE_DIR / 'dataset/review_26045'
BACKUP = REVIEW / 'before_update'
MANIFEST = BASE_DIR / 'dataset/source_registry/curated.json'


def main():
    old = json.loads(MANIFEST.read_text(encoding='utf-8'))
    additions = [s for s in json.loads((REVIEW/'acquisition.json').read_text(encoding='utf-8')) if s['status']=='verified']
    # Validate with the real parser before modifying the manifest or database.
    for s in additions:
        chunks, digest = parse_source(s)
        assert chunks and digest == s['content_hash'], s['source_id']
        print('Validated', s['source_id'], len(chunks), flush=True)
    if not BACKUP.exists():
        BACKUP.mkdir(parents=True)
        shutil.copytree(BASE_DIR/'chroma_db', BACKUP/'chroma_db')
        shutil.copytree(BASE_DIR/'knowledge_base', BACKUP/'knowledge_base')
        shutil.copy2(MANIFEST, BACKUP/'curated.json')
    replaced = {s['source_id'] for s in additions}
    excluded = {'bd_rules_2004', 'ayurveda_aahara', 'fda_botanical'}
    # Unverified local summaries are not evidence if original acquisition failed.
    suspect = {'cgptdm_tk_guidelines','tkdl_csir','ayurveda_aahara_2022','drugs_magic_remedies_1954','fda_botanical_guidance'}
    excluded.update(suspect-replaced)
    removed = [s for s in old if s['source_id'] in excluded or s['source_id'] in replaced]
    active = [s for s in old if s['source_id'] not in excluded and s['source_id'] not in replaced and s['status']=='verified'] + additions
    for s in active:
        if s['source_id']=='wto_trips_agreement': s['kind']='web'
    write_json(REVIEW/'excluded_or_replaced.json', removed)
    write_json(MANIFEST, active)
    results = ingest_manifest()
    errors=[r for r in results if r['status']=='error']
    if errors: raise RuntimeError(str(errors))
    import chromadb
    client=chromadb.PersistentClient(path=str(BASE_DIR/'chroma_db'))
    corpus=client.get_collection(CORPUS_COLLECTION)
    records=corpus.get(include=['metadatas'])
    valid={s['source_id']:s for s in active}
    stale=[key for key,m in zip(records['ids'],records['metadatas']) if m.get('source_id') not in valid]
    if stale: corpus.delete(ids=stale)
    # Repair imported absolute paths without recomputing unchanged embeddings.
    updates=[]
    for key,m in zip(records['ids'],records['metadatas']):
        if m.get('source_id') in valid:
            s=valid[m['source_id']]; correct=str(BASE_DIR/s['local_file_path'])
            if m.get('source')!=correct:
                updates.append((key,dict(m,source=correct)))
    for start in range(0,len(updates),128):
        batch=updates[start:start+128]; corpus.update(ids=[x[0] for x in batch],metadatas=[x[1] for x in batch])
    uploads=client.get_collection('langchain')
    rows=uploads.get(include=['metadatas'])
    out_of_scope={'Cars.xlsx','ML PPT.pptx','artifical intelligence.pdf','CV Resume.pdf','test.txt'}
    ids=[key for key,m in zip(rows['ids'],rows['metadatas']) if Path(m.get('source','')).name in out_of_scope]
    if ids: uploads.delete(ids=ids)
    tracker=BASE_DIR/'knowledge_base/documents.json'
    if tracker.exists():
        tracked=json.loads(tracker.read_text(encoding='utf-8'))
        write_json(tracker,[d for d in tracked if d.get('file_name') not in out_of_scope and (BASE_DIR/'uploaded_documents'/d.get('file_name','')).is_file()])
    state_path=BASE_DIR/'knowledge_base/ingestion.json'
    state=json.loads(state_path.read_text(encoding='utf-8'))
    write_json(state_path,{k:v for k,v in state.items() if k in valid})
    write_json(REVIEW/'changes.json',dict(timestamp=datetime.now(timezone.utc).isoformat(),active_sources=len(active),acquired_sources=len(additions),curated_chunks=corpus.count(),removed_curated_chunks=len(stale),removed_out_of_scope_upload_chunks=len(ids),remaining_upload_chunks=uploads.count(),repaired_source_paths=len(updates),excluded_source_ids=sorted(excluded),backup=str(BACKUP.relative_to(BASE_DIR))))
    print((REVIEW/'changes.json').read_text(),flush=True)

if __name__=='__main__': main()
