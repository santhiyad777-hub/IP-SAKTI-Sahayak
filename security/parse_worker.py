"""Internal parser worker. This is resource isolation, not an OS security sandbox."""
import json
import os
import sys
from pathlib import Path


def main():
    if os.name=='posix':
        import resource
        resource.setrlimit(resource.RLIMIT_AS,(768*1024**2,768*1024**2))
        resource.setrlimit(resource.RLIMIT_CPU,(30,30))
        resource.setrlimit(resource.RLIMIT_FSIZE,(24*1024**2,24*1024**2))
        resource.setrlimit(resource.RLIMIT_NOFILE,(128,128))
    from loaders.document_loader import load_document
    docs=load_document(sys.argv[1])
    if len(docs)>10000 or sum(len(d.page_content) for d in docs)>10*1024*1024:
        raise ValueError('Parsed content exceeds limit')
    Path(sys.argv[2]).write_text(json.dumps([{'text':d.page_content,'metadata':d.metadata} for d in docs]),encoding='utf-8')

if __name__=='__main__':main()
