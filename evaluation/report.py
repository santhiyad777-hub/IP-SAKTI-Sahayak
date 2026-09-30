"""Generate the implementation report from actual evaluation artifacts."""
import json,statistics
from pathlib import Path
from datetime import datetime,timezone
BASE=Path(__file__).resolve().parents[1]
def read(name,fallback):
    p=BASE/name
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else fallback

def main():
    sources=read('dataset/source_registry/curated.json',[])
    live=read('evaluation/live_results.json',[])
    storage=read('evaluation/storage_results.json',{})
    supported=[r for r in live if r.get('expected_sources')]
    negatives=[r for r in live if r.get('expect_abstain')]
    lines=['# IP-SAKTI implementation and verification report','',
        'Report generated: '+datetime.now(timezone.utc).isoformat(),'',
        'The existing app was extended into a citation-grounded domain MVP. Full problem-statement coverage and production certification are not complete.','',
        '## Existing architecture and data','',
        'Streamlit owns the interface and local JSON conversation history. Upload loaders handle PDF, DOCX, PPTX, Excel, CSV, text, Markdown, HTML, JSON and XML. Recursive character splitting uses size 1,000 and overlap 200. CPU MiniLM normalized embeddings feed persistent Chroma. The existing Ollama Cloud model is gpt-oss:120b. Previously, unfiltered top-5 similarity retrieval and an explicit general-knowledge fallback could produce unsupported answers. There are no separate REST API endpoints.','',
        'The inspected domain dataset had 26 registry entries, nine processed document records and 3,478 chunk records. There were 86 duplicate chunk texts and one duplicate full-text record. Stored vectors were 1,024-dimensional BGE-M3 according to the dataset README, incompatible with the existing 384-dimensional collection. Several supposed full texts were navigation or article-title lists. Chunk sizes ranged from 7 to 98,107 characters. PDF page metadata was missing from the processed dataset. The ingestion scripts mentioned by its README were absent.','',
        'This is a factual legal corpus, not a supervised training set. RAG and source refresh are appropriate; no LLM training or fine-tuning was performed. Existing dataset metadata includes jurisdiction, regime, organization, source URL and legal-unit fields. Missing legal-unit labels and unverified dates were not filled with invented values. Sources include English and Hindi material.','',
        'Existing uploads are an AI PDF, an ML slide deck and Cars.xlsx. Cars.xlsx has 303 rows on its populated sheet, 13 columns, 325 missing cells and 14 duplicate rows; its second sheet is empty. These files are not Ayurveda legal authority and remain in uploaded-document mode. The slide deck has 15 slides. The AI PDF has 11 pages, three without extractable text. Before migration the original collection had 95 chunks, including stale references to absent files; absent upload files are excluded from retrieval.','',
        '## Requirement mapping','',
        'Target users: Ayurveda practitioners, researchers, AYUSH startups/MSMEs and cultivators. The MVP provides India/international jurisdiction selection, routing across IP types and regulatory questions, formulation/ABS clarification, source-aware retrieval, supported partial answers, multilingual answer selection, source citations and facilitator/database pointers. Statutes, rules, treaty and official-regulator evidence are kept distinct from user uploads.','',
        '## Implementation','',
        '- Added a separate curated collection inside the existing Chroma database. Both collections retain MiniLM; original incompatible vector files are preserved but not imported.',
        '- Reparsed usable originals with PDF pages. Added controlled PDF acquisition and Crawl4AI web extraction, validated source manifest, content hashes, incremental ingestion and corpus snapshots.',
        '- Added BM25/semantic retrieval, IP-type routing, jurisdiction filtering, selected-upload filtering and multi-regime candidate selection.',
        '- Removed the general-knowledge fallback. Generated claims select real source passages; a second model call checks entailment. Unsupported claims are dropped or the answer abstains. This reduces risk but is not a proof of legal accuracy.',
        '- Preserved conversation history, bookmarks, uploads and exports. PDF export is now on demand and browser-path configurable. Response transformations reuse evidence within the same source/jurisdiction scope.',
        '- Added fixed legal-information notice, local-provider privacy notice, bounded uploads and localhost binding. No subscription access, legal filings or messages to third parties occur.', '',
        '## Files','',
        'Modified: app.py, config.py, requirements.txt, embeddings/embedding_model.py, vectordb/chroma_manager.py, rag/retriever.py, rag/chatbot.py, utils/document_tracker.py, utils/smart_chat.py.','',
        'Added: ingestion/{__init__,pipeline,acquire}.py; evaluation/{__init__,run,check_storage,report}.py and questions/results JSON; tests/{__init__,test_grounding}.py; README.md; this report; .env.example; .gitignore; .streamlit/config.toml; requirements-acquisition.txt; curated source manifest, acquired originals, corpus snapshots and local ingestion state.','',
        'Intentionally preserved: the existing Ollama secret in .env (BHASHINI credentials were added separately); original dataset registry/processed documents/chunks/embeddings; original uploaded document contents; document loaders and splitter; existing framework, LLM and embedding model. Local virtual environment and model cache were created for testing.','',
        '## Actual validation','',
        f'- Live evaluation cases recorded: {len(live)}; runtime errors: {sum(r.get("status")=="error" for r in live)}.',
        f'- Expected-source questions: {len(supported)}; source hit@8: {sum(bool(r.get("hit_at_8")) for r in supported)}/{len(supported)}.',
        f'- Expected-source questions producing answers: {sum(r.get("abstained") is False for r in supported)}/{len(supported)}. Remaining cases abstained; these are not counted as accurate answers.',
        f'- Unsupported-request abstentions: {sum(r.get("abstained") is True for r in negatives)}/{len(negatives)}.',
        f'- Jurisdiction checks passing: {sum(r.get("jurisdiction_pass") is True for r in live)}/{len(live)}.',
        '- All 35 grounding, conversation-language and BHASHINI unit tests passed, including translated-claim rejection, API failure redaction, malformed translation responses and script routing. The original 25 Python files passed syntax parsing; subsequently changed app, chatbot, BHASHINI client and test files also passed.',
        '- pip check reported no broken requirements. The Streamlit process was started on 127.0.0.1:8501.',
        '- The automated Streamlit AppTest command was rejected at approval; it was not rerun through another tool. UI interactions and PDF export remain unverified.', '',
        'Storage verification: `'+json.dumps(storage,sort_keys=True)+'`','']
    bhashini=read('evaluation/bhashini_live_results.json',[])
    if bhashini:
        lines += ['## BHASHINI Udyat integration', '',
            'Added utils/bhashini.py and tests/test_bhashini.py. Configured credentials in ignored .env; preserved the existing Ollama key. The official Dhruva inference endpoint authenticated successfully for English/Hindi/Tamil translations. The Udyat key is stored separately and is not sent as the inference Authorization header.', '',
            'A sidebar toggle enables Hindi/Tamil query translation before retrieval and claim translation before the final evidence audit. Source passages and citations are unchanged. HTTP redirects are refused and remote error bodies are never displayed. English retains the Ollama path. Tanglish output uses BHASHINI Tamil translation and Latin transliteration. Fixed notices and formulation clarifications are localized. Speech is not implemented.', '',
            f'Additional live RAG checks passed: {sum(r.get("passed") is True for r in bhashini)}/{len(bhashini)} (Tamil and Hindi cited answers, English regression, unavailable TKDL abstention). Results: evaluation/bhashini_live_results.json. Passing checks do not establish translation or legal accuracy.', '',
            'Streamlit was restarted to load the credentials and sidebar control. UI interaction tests remain unverified following the earlier declined approval.', '']
    language_flow=read('evaluation/language_flow_results.json',[])
    if language_flow:
        lines += ['## Language correction verification', '',
            'Fixed false language selection from topic words, new Tanglish questions reusing old evidence, lost context after reopening chats, English-only fixed notices, and traditional-knowledge queries excluding the patents collection. Temporary BHASHINI/Ollama transport/server failures now receive bounded retries. Authentication failures are not retried.', '',
            'A live Tanglish answer generated directly by Ollama reversed a negation. Tanglish output now uses evidence-grounded English claims followed by BHASHINI Tamil translation and Latin transliteration; the audit receives the intermediate forms and checks the final text. This addresses the observed failure without claiming perfect translation accuracy.', '',
            'Added utils/language.py, rag/conversation.py, tests/test_language.py and evaluation/language_flow.py. Streamlit and the live evaluation invoke the same conversation function.', '',
            f'Latest conversation checks: {sum(r.get("passed") is True for r in language_flow)}/{len(language_flow)} passed. Artifact: evaluation/language_flow_results.json. Checks cover language/script, expected source retrieval, appropriate answer/refusal and follow-up routing; they are not independent legal or linguistic certification.', '']
    times=[r['seconds'] for r in live if 'seconds' in r]
    if times: lines += [f'Observed live latency: median {statistics.median(times):.2f}s, maximum {max(times):.2f}s. This includes local retrieval and cloud calls, not a controlled production benchmark.','']
    lines += ['These development questions are not a held-out evaluation. Source hit@8 is not answer accuracy, and passing model entailment checks is not independently measured faithfulness. No 100% accuracy claim is made.','',
      '| Test question | Result | Sources |','|---|---|---|']
    for row in live:
        result='error' if row.get('status')=='error' else 'abstained' if row.get('abstained') else 'cited answer'
        lines.append('| '+row['question'].replace('|','/')+' | '+result+' | '+', '.join(row.get('sources',[]))+' |')
    lines += ['', '## Source registry and acquisition results','',
        'Content validation is distinct from legal/current-version validation. Local snapshots may be historical. Unknown publication/effective dates remain unknown.','',
        '| Source | Jurisdiction | Status | Why included / source |','|---|---|---|---|']
    for source in sources:
        lines.append('| '+source['title'].replace('|','/')+' | '+source['jurisdiction']+' | '+source['status']+' | '+source['regime']+'; [original]('+source['source_url']+') |')
    lines += ['', 'Unavailable sources and exact recorded errors:','']
    for source in sources:
        if source.get('status')!='verified': lines.append('- '+source['source_id']+': '+source.get('error','Not yet acquired').replace('\n',' ')[:700])
    lines += ['', '## Remaining limitations and next steps','',
      'The corpus is not an exhaustive current consolidation. Full Ayurveda Aahara regulations, all 2024 patent/biodiversity rule changes, current advertising/labelling/cosmetic/phytopharmaceutical law, pharmacopoeial standards, case law, treaty membership status and all export markets require further primary-source acquisition and review. Some regulator pages are unavailable or return portal HTML. Use the manifest to retry specific sources or ingest an officially downloaded original with its provenance. Do not treat overview pages as the complete legislation.', '',
      'The app now has account authentication and private per-user storage. Application encryption, automatic retention management, comprehensive consent administration, DPDP/AI-standard assessment, voice input/output, knowledge graphs, agentic orchestration and paid-source connectors are not implemented. See SECURITY.md and DEPLOYMENT.md. The problem statement permits staged delivery; these are not silently represented as complete.', '',
      'Run commands, exact environment-variable names, acquisition setup and refresh instructions are in README.md. Current automated and browser validation results are stored under evaluation/. Historical reports do not supersede those results.']
    (BASE/'IMPLEMENTATION_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Wrote IMPLEMENTATION_REPORT.md')
if __name__=='__main__': main()
