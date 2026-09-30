"""File screening and per-account quotas before document parsing."""
import io
import zipfile
from pathlib import Path

ALLOWED={'.pdf','.txt','.csv','.docx','.pptx','.xlsx','.xls','.md','.html','.json','.xml'}

def validate_upload(workspace, name, content):
    path=workspace.upload_path(name)
    if path.suffix.lower() not in ALLOWED:raise ValueError('Unsupported document type.')
    if not content or len(content)>25*1024*1024:raise ValueError('File must contain data and be at most 25 MB.')
    files=[p for p in workspace.uploads.iterdir() if p.is_file()]
    if len(files)>=50 and not path.exists():raise ValueError('Maximum 50 documents per account.')
    existing=path.stat().st_size if path.exists() else 0
    if sum(p.stat().st_size for p in files)-existing+len(content)>100*1024*1024:raise ValueError('Account upload quota is 100 MB.')
    ext=path.suffix.lower()
    if ext=='.pdf' and not content.lstrip().startswith(b'%PDF-'):raise ValueError('Invalid PDF signature.')
    if ext in {'.docx','.xlsx','.pptx'}:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                items=archive.infolist()
                if len(items)>2000 or sum(i.file_size for i in items)>100*1024*1024:raise ValueError('Office document expands beyond the permitted size.')
                if any(i.file_size>max(1,i.compress_size)*200 for i in items):raise ValueError('Unsafe compression ratio.')
                if '[Content_Types].xml' not in archive.namelist():raise ValueError('Invalid Office document.')
        except zipfile.BadZipFile:raise ValueError('Invalid Office document.') from None
    if ext=='.xml' and any(token in content.upper() for token in (b'<!DOCTYPE',b'<!ENTITY')):raise ValueError('XML entities are not supported.')
    return path

# Serialize upload/replace/delete within an account, including quota checks.
import threading
from contextlib import contextmanager
_LOCKS={}
_LOCKS_GUARD=threading.Lock()

@contextmanager
def upload_lock(workspace):
    owner=workspace.owner
    with _LOCKS_GUARD:
        lock,count=_LOCKS.get(owner,(threading.RLock(),0))
        _LOCKS[owner]=(lock,count+1)
    try:
        with lock:yield
    finally:
        with _LOCKS_GUARD:
            lock,count=_LOCKS[owner]
            if count==1:del _LOCKS[owner]
            else:_LOCKS[owner]=(lock,count-1)


def save_upload(workspace,name,content):
    from ingestion.pipeline import ingest_upload
    with upload_lock(workspace):
        path=validate_upload(workspace,name,content)
        previous=path.read_bytes() if path.exists() else None
        try:
            path.write_bytes(content)
            return ingest_upload(path,workspace=workspace)
        except Exception:
            if previous is None:path.unlink(missing_ok=True)
            else:path.write_bytes(previous)
            raise


def delete_upload(workspace,name):
    from vectordb.chroma_manager import delete_document_from_vector_database
    with upload_lock(workspace):
        path=workspace.upload_path(name)
        delete_document_from_vector_database(path,workspace=workspace)
        path.unlink(missing_ok=True)
