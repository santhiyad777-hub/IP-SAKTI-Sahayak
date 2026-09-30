"""Prepare a portable deployment seed containing ONLY verified public corpus rows."""
import gzip
import hashlib
import json
import shutil
from pathlib import Path
import chromadb
from config import BASE_DIR,CHROMA_DB_PATH,CORPUS_COLLECTION


def main():
    target=BASE_DIR/'deploy_assets';target.mkdir(exist_ok=True)
    manifest=json.loads((BASE_DIR/'dataset/source_registry/curated.json').read_text(encoding='utf-8'))
    public={s['source_id']:s.copy() for s in manifest if s.get('status')=='verified'}
    for sid,s in public.items():
        if not sid.replace('_','').replace('-','').isalnum():raise ValueError('Invalid source ID')
        original=(BASE_DIR/s['local_file_path']).resolve()
        if not original.is_relative_to(BASE_DIR/'dataset'):raise ValueError('Source outside dataset')
        destination=target/'sources'/sid/('original'+original.suffix)
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(original,destination)
        s['local_file_path']=destination.relative_to(BASE_DIR).as_posix()
    collection=chromadb.PersistentClient(path=CHROMA_DB_PATH).get_collection(CORPUS_COLLECTION)
    total=0;seen=set()
    seed=target/'corpus.jsonl.gz'
    with gzip.open(seed,'wt',encoding='utf-8') as out:
        for offset in range(0,collection.count(),500):
            rows=collection.get(limit=500,offset=offset,include=['documents','metadatas','embeddings'])
            for key,doc,meta,vector in zip(rows['ids'],rows['documents'],rows['metadatas'],rows['embeddings']):
                sid=meta.get('source_id')
                if sid not in public or meta.get('source_type') not in {'official_pdf','official_web'} or meta.get('owner_id'):
                    raise ValueError('Non-public content detected in curated collection; export stopped')
                meta=dict(meta,source=public[sid]['local_file_path'])
                out.write(json.dumps({'id':key,'document':doc,'metadata':meta,'embedding':vector.tolist()},ensure_ascii=False)+'\n')
                total+=1;seen.add(sid)
    if seen!=set(public):raise ValueError('Public source coverage mismatch')
    (target/'curated.json').write_text(json.dumps(list(public.values()),ensure_ascii=False,indent=2),encoding='utf-8')
    report={'collection':CORPUS_COLLECTION,'chunks':total,'sources':len(seen),'sha256':hashlib.sha256(seed.read_bytes()).hexdigest()}
    (target/'seed.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))

if __name__=='__main__':main()
