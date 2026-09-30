"""Finalize reviewed extraction bounds and metadata, then verify corpus integrity."""
import hashlib
import json
from collections import Counter
from pathlib import Path
import chromadb
from bs4 import BeautifulSoup
from config import BASE_DIR, CORPUS_COLLECTION
from ingestion.pipeline import ingest_manifest, write_json

REVIEW=BASE_DIR/'dataset/review_26045'

def main():
    manifest=BASE_DIR/'dataset/source_registry/curated.json'
    active={s['source_id']:s for s in json.loads(manifest.read_text(encoding='utf-8'))}
    additions=json.loads((REVIEW/'acquisition.json').read_text(encoding='utf-8'))
    for s in additions:
        if s['status']=='verified' and s['source_id'] not in active: active[s['source_id']]=s
    starts={'bd_rules_2024':(49,'MINISTRY OF ENVIRONMENT'), 'bd_rules_amendment_2025':(2,'MINISTRY OF ENVIRONMENT'),
        'ayurveda_aahara_2022':(14,'FOOD SAFETY AND STANDARDS AUTHORITY'),
        'dpdp_rules_2025':(23,'MINISTRY OF ELECTRONICS'), 'fssai_food_claims':(18,'FOOD SAFETY AND STANDARDS AUTHORITY'),
        'fssai_nutraceuticals':(71,'FOOD SAFETY AND STANDARDS AUTHORITY'), 'fssai_labelling':(26,'FOOD SAFETY AND STANDARDS AUTHORITY')}
    for sid,(page,marker) in starts.items():
        active[sid].update(page_start=page,first_page_marker=marker,indexed_language='en',extraction_note='English portion only; original bilingual PDF retained. PDF page numbers unchanged.')
    # Remove navigation only, retaining the actual public CSIR page body verbatim.
    s=active['tkdl_csir'];path=BASE_DIR/s['local_file_path'];soup=BeautifulSoup(path.with_suffix('.html').read_bytes(),'html.parser')
    node=next(x for x in soup.select('.views-row') if 'The Traditional Knowledge Digital Library (TKDL) is a pioneering initiative' in x.get_text())
    path.write_text(node.get_text('\n',strip=True),encoding='utf-8');s['content_hash']=hashlib.sha256(path.read_bytes()).hexdigest()
    s['extracted_characters']=len(path.read_text(encoding='utf-8'));s['extraction_note']='CSIR TKDL content .views-row; navigation excluded'
    for source in active.values():
        source.setdefault("content_hash", hashlib.sha256((BASE_DIR/source["local_file_path"]).read_bytes()).hexdigest())
    write_json(manifest,list(active.values()))
    write_json(REVIEW/"acquisition.json", [active.get(s["source_id"], s) for s in additions])
    results=ingest_manifest();assert not [x for x in results if x['status']=='error'],results
    client=chromadb.PersistentClient(path=str(BASE_DIR/'chroma_db'));corpus=client.get_collection(CORPUS_COLLECTION)
    rows=corpus.get(include=['metadatas','documents']);updates=[]
    for key,m in zip(rows['ids'],rows['metadatas']):
        s=active[m['source_id']];new=dict(m)
        for field in ['title','source_url','jurisdiction','regime','organization','version','retrieved_at','content_hash']:
            if s.get(field) is not None:new[field]=s[field]
        new['source']=str(BASE_DIR/s['local_file_path'])
        if new!=m:updates.append((key,new))
    for start in range(0,len(updates),128):
        batch=updates[start:start+128];corpus.update(ids=[x[0] for x in batch],metadatas=[x[1] for x in batch])
    uploads=client.get_collection('langchain');u=uploads.get(include=['metadatas'])
    stale=[key for key,m in zip(u['ids'],u['metadatas']) if not (BASE_DIR/'uploaded_documents'/Path(m.get('source','')).name).is_file()]
    if stale:uploads.delete(ids=stale)
    rows=corpus.get(include=['metadatas','documents']);counts=Counter(m['source_id'] for m in rows['metadatas'])
    assert set(counts)==set(active)
    assert all(t.strip() for t in rows['documents'])
    assert all(Path(m['source']).is_file() for m in rows['metadatas'])
    assert all(m.get(k) for m in rows['metadatas'] for k in ['source_id','source_url','content_hash','jurisdiction','title'])
    assert all(hashlib.sha256((BASE_DIR/s['local_file_path']).read_bytes()).hexdigest()==s['content_hash'] for s in active.values())
    assert not any('/uni09' in t for t in rows['documents'] if t and len(t)>10), 'Malformed PDF glyph codes remain'
    report=dict(active_sources=len(active),curated_chunks=corpus.count(),remaining_upload_chunks=uploads.count(),
                per_source_chunks=dict(counts),missing_source_files=0,empty_chunks=0,missing_required_metadata=0,
                source_hash_checks='passed',raw_pdf_page_numbers_preserved=True,additional_stale_upload_chunks_removed=len(stale))
    write_json(REVIEW/'verification.json',report)
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':main()
