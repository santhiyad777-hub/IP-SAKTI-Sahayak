"""Persistent Chroma collections with idempotent, document-level replacement."""
import hashlib
from functools import lru_cache
from pathlib import Path
from langchain_chroma import Chroma
from embeddings.embedding_model import get_embedding_model
from config import CHROMA_DB_PATH, CORPUS_COLLECTION

@lru_cache(maxsize=4)
def load_vector_database(collection_name=CORPUS_COLLECTION):
    if collection_name != CORPUS_COLLECTION:raise PermissionError("Use an authenticated private workspace.")
    return Chroma(collection_name=collection_name, persist_directory=CHROMA_DB_PATH,
                  embedding_function=get_embedding_model())

def create_or_update_vector_database(chunks, collection_name="langchain", source_id=None, workspace=None):
    if not chunks:
        raise ValueError("No readable document chunks were provided.")
    if workspace is not None:
        owner=workspace.owner
        for doc in chunks:
            path=Path(doc.metadata["source"]).resolve()
            if path.parent!=workspace.uploads.resolve():raise PermissionError("Upload is outside this account.")
            doc.metadata["owner_id"]=owner
        db=load_private_database(workspace)
    else:
        if collection_name != CORPUS_COLLECTION:raise PermissionError("Authentication required for private indexing.")
        db = load_vector_database(collection_name)
    source_id = source_id or chunks[0].metadata.get("source_id") or str(Path(chunks[0].metadata["source"]).resolve())
    ids = []
    for i, doc in enumerate(chunks):
        doc.metadata["source_id"] = source_id
        ids.append(hashlib.sha256((source_id + str(i) + doc.page_content).encode()).hexdigest())
    existing = set(db.get(where={"source_id": source_id})["ids"])
    if workspace is not None and db._collection.count()-len(existing)+len(ids)>10000:
        raise ValueError("Account index limit reached. Remove an old document first.")
    # Upsert first: a failed batch leaves the old version available. Retry is idempotent.
    try:
        for start in range(0, len(chunks), 128):
            batch = [(d, key) for d, key in zip(chunks[start:start+128], ids[start:start+128]) if key not in existing]
            if batch:
                db.add_documents([d for d, _ in batch], ids=[key for _, key in batch])
    except Exception:
        # Remove only newly inserted IDs; retain the previous version on failure.
        inserted=set(db.get(where={"source_id":source_id})["ids"])-existing
        if inserted:db.delete(ids=list(inserted))
        raise
    obsolete = list(existing - set(ids))
    if obsolete:
        db.delete(ids=obsolete)
    # Migrate legacy random IDs for this upload only after successful indexing.
    if collection_name == "langchain":
        path = Path(chunks[0].metadata["source"])
        for variant in {str(path), str(Path("uploaded_documents") / path.name)}:
            old = db.get(where={"source": variant})
            stale = [key for key in old["ids"] if key not in ids]
            if stale:
                db.delete(ids=stale)
    return db

def delete_document_from_vector_database(file_path, workspace=None):
    if workspace is None:raise PermissionError("Authentication required for private documents.")
    path=Path(file_path).resolve()
    if path.parent!=workspace.uploads.resolve():raise PermissionError("Upload is outside this account.")
    db = load_private_database(workspace)
    for source in {str(path), str(path.resolve()), str(Path("uploaded_documents") / path.name)}:
        db.delete(where={"source": source})


@lru_cache(maxsize=32)
def _private_database(path):
    return Chroma(collection_name="documents",persist_directory=path,embedding_function=get_embedding_model())


def load_private_database(workspace):
    # Resolving vectors validates the current session, even on a cache hit.
    return _private_database(str(workspace.vectors))
