"""Controlled official-source acquisition. Run separately with Crawl4AI installed.
No restricted subscriptions, TKDL content, off-domain redirects, or robots bypasses.
"""
import argparse, asyncio, hashlib, io, json, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urljoin, unquote
from urllib.robotparser import RobotFileParser
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
BASE=Path(__file__).resolve().parents[1]
MANIFEST=BASE/'dataset/source_registry/curated.json'
HOSTS={'ipindia.gov.in','indiacode.gov.in','indiacode.nic.in','nbaindia.nic.in','nbaindia.org','wipo.int','cbd.int','wto.org','fssai.gov.in','cdsco.gov.in','plantauthority.gov.in','copyright.gov.in','ema.europa.eu','fda.gov','gov.uk','egazette.gov.in','ccras.nic.in','csir.res.in','pcimh.gov.in','sci.gov.in','meity.gov.in','assam.gov.in','nist.gov'}
AGENT='IP-SAKTI-Research/1.0'
SESSION=requests.Session(); SESSION.headers['User-Agent']=AGENT
ROBOTS={}
def allowed(url):
    u=urlparse(url); host=u.hostname or ''
    return u.scheme=='https' and not u.username and (u.port is None or u.port==443) and any(host==h or host.endswith('.'+h) for h in HOSTS)

def get(url, **kwargs):
    for _ in range(6):
        if not allowed(url): raise ValueError('Unapproved URL')
        r=SESSION.get(url,timeout=40,allow_redirects=False,**kwargs)
        if r.is_redirect: url=urljoin(url,r.headers['Location']); continue
        r.raise_for_status(); return r
    raise ValueError('Too many redirects')

def robots_ok(url):
    u=urlparse(url); base=f'{u.scheme}://{u.netloc}'
    if base not in ROBOTS:
        r=SESSION.get(base+'/robots.txt',timeout=25,allow_redirects=False)
        parser=RobotFileParser()
        if r.status_code==404: parser.parse([])
        elif r.status_code==200: parser.parse(r.text.splitlines())
        else: raise ValueError('robots.txt unavailable; crawl not attempted')
        ROBOTS[base]=parser
    if not ROBOTS[base].can_fetch(AGENT,url): raise ValueError('robots_disallowed')

def clean(html):
    soup=BeautifulSoup(html,'html.parser')
    for tag in soup.select('script,style,nav,header,footer,aside,form,noscript'): tag.decompose()
    main=soup.select_one('main') or soup.select_one('article') or soup.body or soup
    text=main.get_text('\n',strip=True)
    if 'Chapters & Sections' in text:
        lines=text.splitlines()
        end=max((i for i,line in enumerate(lines) if re.fullmatch(r'(Section|Rule) [0-9A-Za-z-]+',line.strip())),default=-1)
        if end>=0: text='\n'.join(lines[end+1:])
    return text

def save_manifest(rows):
    MANIFEST.parent.mkdir(parents=True,exist_ok=True)
    tmp=MANIFEST.with_suffix('.tmp'); tmp.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(MANIFEST)

def source(sid,title,url,jurisdiction,regime,patterns,kind='pdf',organization=None):
    return dict(source_id=sid,title=title,source_url=url,jurisdiction=jurisdiction,regime=regime,
        organization=organization or urlparse(url).hostname,required_patterns=patterns,kind=kind,status='pending')

def seeds():
    rows=[]
    old=json.loads((BASE/'dataset/source_registry/registry.json').read_text(encoding='utf-8'))['sources']
    # Actual originals retained. Existing web table-of-contents and portal dumps excluded.
    for x in old:
        if x['source_id'] in {'ip_india_gi_act','bd_amendment_act_2023_gazette','cdsco_drugs_cosmetics_act_1940','wto_trips_agreement'}:
            s=source(x['source_id'],x['title'],x['official_url'],x['jurisdiction'],x['regime'],[],organization=x['organization'])
            s.update(local_file_path=x['local_file_path'].replace('\\','/'),status='verified',retrieved_at=x['last_checked'],version='Existing snapshot; not a current consolidation')
            rows.append(s)
    rows.extend([
      source('patents_act','Patents Act 1970','https://www.indiacode.nic.in/bitstream/123456789/1392/1/a197039.pdf','india','patents',['traditional knowledge','patent']),
      source('nagoya_full','Nagoya Protocol full text','https://www.cbd.int/abs/doc/protocol/nagoya-protocol-en.pdf','international','biodiversity_abs',['prior informed consent','Article 6']),
      source('gr atk'.replace(' ',''),'WIPO GRATK Treaty','https://www.wipo.int/documents/d/treaties/docs-en-gratk.pdf','international','traditional_knowledge',['disclosure','Article 3']),
      source('abs_2025','Biological Diversity ABS Regulations 2025','https://www.nbaindia.nic.in/sites/default/files/2026-07/GNABSREG_2025.pdf','india','biodiversity_abs',['2025','benefit']),
      source('ayurveda_aahara_2022','Ayurveda Aahara Regulations 2022','https://fssai.gov.in/upload/notifications/2022/05/62789a20b54bdGazette_Notification_Ayurveda_Aahara_09_05_2022.pdf','india','food_regulation',['Ayurveda','labell']),
      source('nba_faq','NBA official frequently asked questions','https://www.nbaindia.nic.in/about-us/faqs','india','biodiversity_abs',['Section 3','2024'],'web'),
      source('patents_3','Patents Act: inventions not patentable','https://ipindia.gov.in/acts/patent-act-1970/section-3','india','patents',['traditional knowledge'],'web'),
      source('patent_rule_24b','Patents Rules: examination of application (Rule 24B)','https://ipindia.gov.in/acts/patent-rules-2003/rule-24b','india','patents',['2024','examination'],'web'),
      source('wipo_pct_guide','PCT international patent system','https://www.wipo.int/en/web/pct-system','international','patents',['international','patent'],'web'),
      source('wipo_madrid_guide','Madrid international trademark system','https://www.wipo.int/en/web/madrid-system','international','trademarks',['international','trademark'],'web'),
      source('wipo_hague_guide','Hague international design system','https://www.wipo.int/en/web/hague-system','international','designs',['international','design'],'web'),
      source('wipo_trade_secrets','WIPO trade secrets overview','https://www.wipo.int/en/web/trade-secrets','international','trade_secrets',['confidential','secret'],'web'),
    ])
    return rows

async def acquire(refresh=False, only=None):
    previous={s['source_id']:s for s in json.loads(MANIFEST.read_text(encoding='utf-8'))} if MANIFEST.exists() else {}
    rows=[previous.get(s['source_id'],s) for s in seeds()]
    # Keep manually reviewed additions across refreshes.
    ids={s['source_id'] for s in rows}; rows += [s for k,s in previous.items() if k not in ids]
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    async with AsyncWebCrawler(config=BrowserConfig(headless=True,verbose=False,user_agent=AGENT)) as crawler:
        for s in rows:
            if only and s['source_id'] not in only: continue
            if s.get('status')=='verified' and not refresh: continue
            stamp=datetime.now(timezone.utc).isoformat()
            try:
                if s.get('kind')=='pdf':
                    r=get(s['source_url'])
                    if s.get('resolve_pdf'):
                        soup=BeautifulSoup(r.content,'html.parser')
                        node=soup.select_one('a[href*="/laws/en/in/"][href*=".pdf"]') or soup.select_one('iframe[src],object[data],embed[src]')
                        if not node: raise ValueError('No original document embedded in official record')
                        target=urljoin(r.url,node.get('href') or node.get('src') or node.get('data'))
                        s['record_url']=s['source_url']
                        r=get(target)
                    data=r.content
                    if len(data)>40*1024*1024: raise ValueError('PDF exceeds 40MB limit')
                    if not data.startswith(b'%PDF-'): raise ValueError('Expected PDF, received portal/HTML')
                    text='\n'.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(data)).pages)
                    name=Path(unquote(urlparse(r.url).path)).name
                    name=re.sub(r'[<>:"/\\|?*]','_',name)
                    path=BASE/'dataset/raw/official'/s['source_id']/name
                    s['source_url']=s.get('record_url',r.url)
                else:
                    robots_ok(s['source_url'])
                    # Validate redirects before the browser receives the page.
                    r=get(s['source_url']); robots_ok(r.url)
                    result=await crawler.arun(url=r.url,config=CrawlerRunConfig(check_robots_txt=True,
                        excluded_tags=['nav','header','footer','aside','form'],cache_mode=CacheMode.BYPASS,
                        page_timeout=60000,max_retries=1,verbose=False))
                    if not result.success: raise ValueError('Crawl failed: '+str(result.error_message)[:1000])
                    if not allowed(result.url): raise ValueError('Unapproved final URL')
                    text=clean(result.html)
                    data=text.encode('utf-8'); path=BASE/'dataset/raw/official'/s['source_id']/'content.txt'
                    s['source_url']=result.url
                    links=[{'text':a.get('text',''),'url':a.get('href','')} for a in result.links.get('internal',[]) if allowed(a.get('href',''))]
                    s['discovered_links']=links[:150]
                    s['page_title']=(result.metadata or {}).get('title',s['title'])
                if len(text)<250 or not all(re.search(p,text,re.I) for p in s['required_patterns']):
                    raise ValueError('Expected substantive content absent')
                digest=hashlib.sha256(data).hexdigest()
                path.parent.mkdir(parents=True,exist_ok=True)
                if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
                    # Retain previous bytes when an official document changes.
                    if path.exists():
                        old_hash=hashlib.sha256(path.read_bytes()).hexdigest()
                        archive=path.parent/(old_hash[:12]+'_'+path.name)
                        if not archive.exists(): archive.write_bytes(path.read_bytes())
                    path.write_bytes(data)
                s.update(status='verified',local_file_path=path.relative_to(BASE).as_posix(),content_hash=digest,retrieved_at=stamp,last_checked=stamp)
                s.pop('error',None)
            except Exception as exc:
                # Keep an existing validated snapshot, but clearly record refresh failure.
                s['status']='verified' if s.get('local_file_path') and s.get('status')=='verified' else 'unavailable'
                s.update(error=str(exc)[:1000],last_checked=stamp)
            print(s['source_id'],s['status'],s.get('error',''),flush=True)
            save_manifest(rows)
            await asyncio.sleep(1)
    save_manifest(rows)

if __name__=='__main__':
    p=argparse.ArgumentParser(description="Fetch approved official sources and optionally index them for grounded answers.")
    p.add_argument('--refresh',action='store_true',help='Check approved sources again and retain the prior verified copy if a refresh fails.')
    p.add_argument('--only',nargs='*',help='Fetch only these source IDs from the approved registry.')
    p.add_argument('--ingest',action='store_true',help='Index verified sources after acquisition so they are available to the chatbot.')
    args=p.parse_args()
    asyncio.run(acquire(args.refresh,args.only))
    if args.ingest:
        # Import only after collection: this keeps acquisition usable on machines
        # where the chatbot's embedding stack has not been installed yet.
        from ingestion.pipeline import ingest_manifest
        summary=ingest_manifest()
        indexed=sum(item.get('status') == 'indexed' for item in summary)
        print(f'Indexed {indexed} updated official source(s).',flush=True)
