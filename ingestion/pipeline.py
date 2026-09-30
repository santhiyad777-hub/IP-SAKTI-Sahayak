"""Versioned ingestion of reviewed originals; no precomputed incompatible vectors."""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from langchain_core.documents import Document
from bs4 import BeautifulSoup
from config import BASE_DIR, CORPUS_COLLECTION, EMBEDDING_MODEL, UPLOAD_FOLDER
from loaders.document_loader import load_document
from utils.splitter import split_documents
from vectordb.chroma_manager import create_or_update_vector_database
MANIFEST=BASE_DIR/"dataset/source_registry/curated.json"
STATE=BASE_DIR/"knowledge_base/ingestion.json"

def write_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    tmp.replace(path)

def clean_html(raw):
    soup=BeautifulSoup(raw,"html.parser")
    for tag in soup.select("script,style,nav,header,footer,aside,form,noscript"): tag.decompose()
    main=soup.select_one("main") or soup.select_one("article") or soup.body or soup
    return main.get_text("\n",strip=True)

def parse_source(source):
    path=BASE_DIR/source["local_file_path"]
    if not path.resolve().is_relative_to(BASE_DIR): raise ValueError("Source path outside project")
    if path.suffix.lower()==".pdf": docs=load_document(str(path))
    elif path.suffix.lower() in {".html",".htm"}:
        raw=path.read_bytes()
        from bs4 import UnicodeDammit
        docs=[Document(page_content=clean_html(UnicodeDammit(raw).unicode_markup or ""))]
    else: docs=[Document(page_content=path.read_text(encoding="utf-8"))]
    if "page_start" in source:
        docs = [d for d in docs if d.metadata.get("page", 0) >= source["page_start"]]
    if source.get("first_page_marker") and docs:
        marker = source["first_page_marker"]
        if marker not in docs[0].page_content: raise ValueError("English start marker missing")
        docs[0].page_content = docs[0].page_content[docs[0].page_content.index(marker):]
    text=" ".join(d.page_content for d in docs)
    if not all(re.search(pattern,text,re.I) for pattern in source.get("required_patterns",[])):
        raise ValueError("Content validation failed: expected provisions absent")
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    result=[]
    for doc in docs:
        doc.page_content=re.sub(r"[ \t]+"," ",doc.page_content).strip()
        if len(doc.page_content)<40: continue
        meta={k:v for k,v in source.items() if k in {"source_id","title","organization","jurisdiction","regime","source_url","retrieved_at","version","publication_date"} and v is not None}
        doc.metadata.update(meta, source=str(path),source_type="official_pdf" if path.suffix==".pdf" else "official_web",content_hash=digest)
        # Only label explicit headings; page references remain the primary PDF locator.
        headings=re.findall(r"(?im)^\s*((?:Article|Section|Rule)\s+\d+[A-Za-z]*(?:[.: -].{0,100})?)$",doc.page_content)
        if headings: doc.metadata["section"]="; ".join(headings)[:250]
        result.append(doc)
    return split_documents(result),digest

def ingest_manifest():
    manifest=json.loads(MANIFEST.read_text(encoding="utf-8"))
    state=json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    summary=[]
    seen=set()
    for source in manifest:
        if source.get("status")!="verified": continue
        try:
            path=BASE_DIR/source["local_file_path"]
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            if digest in seen: summary.append({"source":source["source_id"],"status":"duplicate"}); continue
            seen.add(digest)
            version=digest+EMBEDDING_MODEL+"parser-v1"
            if "page_start" in source: version += ":page-start="+str(source["page_start"])+":"+source.get("first_page_marker", "")
            if state.get(source["source_id"],{}).get("version")==version:
                summary.append({"source":source["source_id"],"status":"unchanged"}); continue
            chunks,_=parse_source(source)
            create_or_update_vector_database(chunks,CORPUS_COLLECTION,source["source_id"])
            state[source["source_id"]]={"version":version,"chunks":len(chunks),"indexed_at":datetime.now(timezone.utc).isoformat()}
            write_json(STATE,state)
            summary.append({"source":source["source_id"],"status":"indexed","chunks":len(chunks)})
        except Exception as exc:
            summary.append({"source":source["source_id"],"status":"error","error":str(exc)})
        print(summary[-1],flush=True)
    write_json(BASE_DIR/"knowledge_base/ingestion_report.json",summary)
    snapshot=BASE_DIR/"dataset/corpus_versions"/datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")/"curated.json"
    write_json(snapshot,manifest)
    return summary

def ingest_upload(path, workspace=None):
    if workspace is None:raise PermissionError("Authentication required for private uploads.")
    path=Path(path).resolve()
    if path.parent!=workspace.uploads.resolve(): raise ValueError("Upload must be inside this account")
    from security.parser import parse_private_document
    docs=parse_private_document(path)
    for doc in docs: doc.metadata.update(source_type="upload",jurisdiction="unspecified",title=path.name,source_id=str(path))
    chunks=split_documents(docs)
    if len(chunks)>4000:raise ValueError("Document contains too many chunks.")
    create_or_update_vector_database(chunks,source_id=str(path),workspace=workspace)
    return len(chunks)

if __name__=="__main__":
    ingest_manifest()
