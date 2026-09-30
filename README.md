# IP-SAKTI Sahayak

An Ayurveda IP and regulatory RAG workspace extending the existing Streamlit app. The original Ollama `gpt-oss:120b`, MiniLM embeddings and persistent Chroma database are retained. This is a source-grounded MVP, not a complete or certified legal-advice product.

## Run

Open a terminal in this directory (the inner `RAG CHATBOT LANGUVAGE` directory):

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Run `powershell -ExecutionPolicy Bypass -File .\Start-IPSAKTI.ps1` to use the isolated environment on http://127.0.0.1:8502. Select **India** or **International** and an answer language. Source selection is automatic; the removed source-mode dropdown stays hidden. The knowledge base is available without a new upload. The formulation/ABS panel collects missing facts before assigning a category. Existing conversations, bookmarks, exports and document uploads remain available. Regenerate and reformat/translate requests pass through the evidence checks.

For a fresh Python 3.11 environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt torch==2.5.1 --extra-index-url https://download.pytorch.org/whl/cpu
```

The only required secret is `OLLAMA_API_KEY`, in this directory's `.env` or your environment. The existing `.env` was preserved. Optional settings: `OLLAMA_HOST` (default `https://ollama.com`), `LLM_MODEL` (default `gpt-oss:120b`), `MIN_SEMANTIC_SCORE` (default `0.30`, a retrieval threshold, not a confidence probability), and `CHROME_PATH` for PDF export. See `.env.example`. Cached MiniLM weights are used locally after the first download.

## Refresh and ingest

The app environment is separate from the acquisition environment because Crawl4AI has its own browser and dependency requirements. The current acquisition run used the installed system Crawl4AI 0.9.3. To reproduce it in an isolated environment:

```powershell
python -m venv .venv-crawl
.\.venv-crawl\Scripts\python.exe -m pip install -r requirements-acquisition.txt
.\.venv-crawl\Scripts\python.exe -m playwright install chromium
.\.venv-crawl\Scripts\python.exe -u ingestion/acquire.py
# Recheck existing sources explicitly:
.\.venv-crawl\Scripts\python.exe -u ingestion/acquire.py --refresh
.\.venv\Scripts\python.exe -u -m ingestion.pipeline --uploads
```

Acquisition uses a bounded list of official sources, validates PDFs and substantive content, honors robots checks for crawling, and records unavailable sources. `--only SOURCE_ID ...` limits acquisition. Newly discovered links are recorded for review, not indiscriminately crawled. TLS verification remains enabled. No TKDL or subscription contents are accessed.

`dataset/source_registry/curated.json` is the active acquisition manifest. `verified` means content was successfully obtained and passed the configured checks; it does **not** certify legal currency or applicability. Unknown publication/effective dates are not invented. Source URLs, retrieval timestamps and content hashes are retained. Original dataset files and the original source registry remain available for comparison. The curated corpus uses the `ip_sakti_v1` Chroma collection; uploads use the original `langchain` collection. Both use 384-dimensional MiniLM vectors. The old 1,024-dimensional dataset vectors are not mixed into either collection.

Ingestion skips unchanged originals, batches new embeddings, uses deterministic chunk IDs, and replaces outdated chunks only after successful upserts. Corpus snapshots and an ingestion report are written locally. Run ingestion after reviewing source changes; no scheduled refresh is silently installed. Uploads are indexed incrementally through the existing UI. Empty/unreadable uploads report errors; scanned pages without text require OCR or an accessible original.

## Evidence and retrieval

Queries are routed by IP/regulatory type and filtered by jurisdiction before semantic and BM25 retrieval. Multi-regime queries retain candidates from each relevant regime. PDF evidence expands to its cited page to preserve qualifications. Sources may still disagree or be out of date.

The LLM selects numbered source passages for each claim. The application resolves these to actual source text, validates references, then runs a separate entailment check. Only supported claims are displayed, with a partial-answer notice if needed. Missing evidence produces an explicit abstention. Citations include original URLs, PDF page indexes (one-based), available headings and upload locations. The evidence-status indicator is not a calibrated confidence score.

The global language selector offers Auto, English, Tamil and Hindi. Tanglish is not an output option. A selected language controls the interface and every new answer regardless of the question language; Auto follows the question. Tamil written in Latin letters can still be understood as input and receives Tamil output in Auto mode.

Every assistant message has its own language selector. It changes that answer only, using its original content and stored context without a new retrieval. Original answers, source URLs, citation identifiers and page references remain intact. Versions are cached persistently in the existing conversation JSON. An individual override takes priority for that message; other messages follow the global language.

## Tests and measured results

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -u -m evaluation.run
.\.venv\Scripts\python.exe -u -m evaluation.run --live
.\.venv\Scripts\python.exe -u -m evaluation.check_storage
```

`--live` sends evaluation questions and retrieved excerpts to the configured Ollama service. `--trace` saves evaluation diagnostics locally. Results are in `evaluation/live_results.json`, `retrieval_results.json` and `storage_results.json`; the detailed implementation report is `IMPLEMENTATION_REPORT.md`. Source hit/recall measurements are not answer accuracy. The test questions were used during development and are not a held-out benchmark. Multilingual legal terminology and all production decisions require expert review.

The latest isolated Streamlit UI tests exercise language selection, Auto greetings and repeated individual-message switching without touching real chat history. Native browser rendering and PDF printing are separate from these UI-state tests.

## Privacy and deployment limits

Registration and sign-in now gate all private workspace content. Each account has owner-scoped conversations, preferences, documents, vector storage and exports. Questions and retrieved excerpts go to the configured Ollama provider; optional translations use Bhashini. Server files are not application-encrypted. See [SECURITY.md](SECURITY.md) for controls and limits and [DEPLOYMENT.md](DEPLOYMENT.md) for Render/Railway deployment. Local startup remains bound to localhost.

Official database and facilitator links are navigation pointers; the app does not claim to search TKDL, confirm live registry status, file applications or connect paid subscriptions. Subscription access requires a future connector with explicit, logged consent. Full current-law coverage, case-law curation, pharmacopoeial standards and complete export-market coverage remain gaps. Consult the active manifest for exact acquisition failures. Information only, not legal advice.


## BHASHINI and message translations

Store secrets in the ignored local `.env` using `BHASHINI_UDYAT_KEY` and
`BHASHINI_INFERENCE_KEY`. Existing `_API_KEY` names remain read-compatible.
The original Ollama key and models are retained. No keys are included in frontend code.

BHASHINI translates questions for English-oriented retrieval and translates grounded
answer claims. Existing Ollama performs generation and evidence checks. Translation
protects statutory identifiers, numbers, acronyms and URLs. Temporary service failures
receive bounded retries; the configured Ollama translator is a fallback. A failed
meaning/reference check reports an error instead of storing an unverified version.

Central interface strings: `utils/ui_strings.json`; language routing and notices:
`utils/language.py`; message versions: `utils/message_versions.py`.
Each assistant message retains `message_id`, `conversation_id`, `original_question`,
`original_answer`, `answer_language`, `retrieved_context`, `sources`,
`translated_versions` and an optional `display_language` override. Existing chats
are migrated when loaded. User-authored questions and original document names stay
intact. Chat exports use the currently displayed answer versions.

Questions, relevant excerpts and translation text are sent to the configured services.
Chat history, source context and versions remain in the existing local JSON storage.
No new database or REST framework was introduced. Restart Streamlit after changing keys.

Run current verification:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -u -m evaluation.multilingual_final
```

The live runner tests selected-language answers, Auto, repeated individual-message
switches, reference preservation, real document ingestion and unsupported questions.
It uses a temporary copy of an existing official source and removes its test index/file.
Results: `evaluation/multilingual_final_results.json`. Earlier language-flow artifacts
record development versions, including the now-removed Tanglish output.

API reference: https://bhashini-developer-portal-dev.bhashini.co.in/docs/api/text-to-text


## SIH26045 workflow additions

Open **Product brief & review tools** above the chat. Save product facts per conversation, then request classification or an ABS review. Unknown fields stay unknown; the form itself makes no legal decision. These requests use the same retrieval and citation checks as chat.

Every answer has an evidence status. **Evidence passport** exposes only reference numbers found in that answer, with stored source excerpts, pages, retrieval dates and document hashes; it can be downloaded as JSON. It does not represent a calibrated confidence score or independent legal verification.

**Source freshness** shows the manifest for the selected jurisdiction, including missing files, retrieval age and version notes. **Expert review** exports a user-controlled Markdown handoff with original answers and citations and links to the WIPO TISC directory. Nothing is sent automatically. The **Privacy & audit** tab explains provider processing/local storage and exports a content-free metadata audit. Paid connectors remain disabled.

See `SETUP.md`, `SIH26045_COMPLETION_REPORT.md`, and `DEMO_GUIDE.md` for reproducible checks and remaining limitations.
