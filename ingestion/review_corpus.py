"""Acquire reviewed SIH26045 sources without generating or paraphrasing authority.

Run with --fetch to download the explicitly listed public sources. Acquisition
results are staged for review; the active manifest is not changed by this step.
"""
import argparse
import hashlib
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

BASE = Path(__file__).resolve().parents[1]
REVIEW = BASE / 'dataset/review_26045'
HOSTS = {'cbd.int', 'wipo.int', 'cdsco.gov.in', 'fssai.gov.in',
         'indiacode.nic.in', 'ipindia.gov.in', 'fda.gov', 'gov.uk',
         'csir.res.in', 'assam.gov.in', 'pcimh.gov.in', 'sci.gov.in', 'meity.gov.in',
         'nvlpubs.nist.gov', 'nist.gov', 'egazette.gov.in'}


def get(url):
    for _ in range(6):
        host = urlparse(url).hostname or ''
        if not url.startswith('https://') or not any(host == h or host.endswith('.' + h) for h in HOSTS):
            raise ValueError('Unapproved source URL: ' + url)
        response = requests.get(url, timeout=45, allow_redirects=False,
                                headers={'User-Agent': 'IP-SAKTI-Research/1.0'})
        if response.is_redirect:
            url = urljoin(url, response.headers['Location'])
            continue
        response.raise_for_status()
        return response
    raise ValueError('Too many redirects')


def fetch(source):
    source = dict(source)
    try:
        response = get(source['source_url'])
        if source.get('resolve_pdf'):
            soup = BeautifulSoup(response.content, 'html.parser')
            node = soup.select_one('a[href*="/laws/en/"][href*=".pdf"], iframe[src*=".pdf"], a[href*="/treaties/en/"][href*=".pdf"]')
            if node is None:
                raise ValueError('Official record has no English PDF')
            response = get(urljoin(response.url, node.get('href', node.get('src'))))
        data = response.content
        folder = BASE / 'dataset/raw/official' / source['source_id']
        if source['kind'] == 'pdf':
            if not data.startswith(b'%PDF-'):
                raise ValueError('Expected original PDF, received another format')
            reader = PdfReader(io.BytesIO(data))
            text = '\n'.join(page.extract_text() or '' for page in reader.pages)
            source['page_count'] = len(reader.pages)
            path = folder / 'original.pdf'
        else:
            soup = BeautifulSoup(data, 'html.parser')
            for tag in soup.select('script,style,nav,header,footer,aside,form,noscript'):
                tag.decompose()
            main = soup.select_one('main') or soup.select_one('article') or soup.body or soup
            text = main.get_text('\n', strip=True)
            path = folder / 'original.txt'
        if len(text) < 400 or not all(re.search(pattern, text, re.I) for pattern in source['required_patterns']):
            raise ValueError('Substantive content validation failed')
        folder.mkdir(parents=True, exist_ok=True)
        if source['kind'] != 'pdf':
            (folder / 'original.html').write_bytes(data)
            source['raw_content_hash'] = hashlib.sha256(data).hexdigest()
            data = text.encode('utf-8')
        path.write_bytes(data)
        source.update(status='verified', local_file_path=path.relative_to(BASE).as_posix(),
                      content_hash=hashlib.sha256(data).hexdigest(),
                      retrieved_at=datetime.now(timezone.utc).isoformat(),
                      download_url=response.url.split('?')[0], extracted_characters=len(text),
                      provenance='Downloaded original; extracted without paraphrasing')
    except Exception as exc:
        source.update(status='unavailable', error=str(exc))
    print(source['source_id'], source['status'], source.get('error', ''), flush=True)
    return source


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fetch', action='store_true')
    parser.add_argument('--only', nargs='*')
    args = parser.parse_args()
    if not args.fetch:
        parser.error('Use --fetch to acquire the reviewed candidate list')
    candidates = json.loads((REVIEW / 'candidates.json').read_text(encoding='utf-8'))
    previous = REVIEW / 'acquisition.json'
    results = {s['source_id']: s for s in json.loads(previous.read_text(encoding='utf-8'))} if previous.exists() else {}
    selected = [s for s in candidates if (not args.only or s['source_id'] in args.only)
                and results.get(s['source_id'], {}).get('status') != 'verified']
    with ThreadPoolExecutor(max_workers=4) as pool:
        for source in pool.map(fetch, selected):
            results[source['source_id']] = source
            previous.write_text(json.dumps(list(results.values()), ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
