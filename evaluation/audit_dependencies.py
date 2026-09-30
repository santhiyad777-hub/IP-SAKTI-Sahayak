"""Audit installed package versions against PyPI's published vulnerability records."""
import concurrent.futures
import importlib.metadata
import json
import requests
from datetime import datetime,timezone
from pathlib import Path


def check(item):
    name,version=item
    try:
        response=requests.get(f'https://pypi.org/pypi/{name}/{version}/json',timeout=20)
        response.raise_for_status();data=response.json()
        return {'name':name,'version':version,'vulnerabilities':data.get('vulnerabilities',[])}
    except Exception as error:return {'name':name,'version':version,'error':type(error).__name__}

def main():
    packages=sorted({(d.metadata['Name'],d.version.split('+')[0]) for d in importlib.metadata.distributions()})
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:rows=list(pool.map(check,packages))
    findings=[r for r in rows if r.get('vulnerabilities')];errors=[r for r in rows if r.get('error')]
    result={'passed':not findings and not errors,'checked_at':datetime.now(timezone.utc).isoformat(),'source':'PyPI version JSON vulnerability records','packages_checked':len(rows),'findings':findings,'lookup_errors':errors}
    Path('evaluation/dependency_security.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'packages':len(rows),'findings':[(r['name'],r['version'],len(r['vulnerabilities'])) for r in findings],'errors':errors},indent=2))
    raise SystemExit(1 if findings or errors else 0)
if __name__=='__main__':main()
