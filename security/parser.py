"""Bound untrusted parsing in a disposable subprocess; never send it credentials."""
import json
import os
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from langchain_core.documents import Document


_SLOTS=threading.BoundedSemaphore(1)

@contextmanager
def parsing_slot():
    if not _SLOTS.acquire(timeout=5):raise ValueError('Document processing is busy. Retry shortly.')
    try:yield
    finally:_SLOTS.release()


def parse_private_document(path):
    path=Path(path).resolve()
    with parsing_slot(), tempfile.TemporaryDirectory(prefix='parse-',dir=path.parent.parent) as temporary:
        output=Path(temporary)/'parsed.json'
        # Python/Windows startup variables only. No API keys or application secrets.
        env={k:v for k,v in os.environ.items() if k.upper() in {'PATH','SYSTEMROOT','WINDIR','TEMP','TMP','LANG','LC_ALL','VIRTUAL_ENV'}}
        env.update(PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
        try:
            completed=subprocess.run([sys.executable,'-m','security.parse_worker',str(path),str(output)],
                cwd=str(Path(__file__).resolve().parents[1]),env=env,stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=45,check=False)
        except subprocess.TimeoutExpired:
            raise ValueError('Document parsing exceeded the time limit.') from None
        if completed.returncode or not output.exists() or output.stat().st_size>24*1024*1024:
            raise ValueError('Document could not be parsed within the permitted limits.')
        rows=json.loads(output.read_text(encoding='utf-8'))
    return [Document(page_content=r['text'],metadata={**r['metadata'],'source':str(path)}) for r in rows]
