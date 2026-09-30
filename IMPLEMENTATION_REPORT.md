> Multilingual follow-up: see [MULTILINGUAL_REPORT.md](MULTILINGUAL_REPORT.md) for the current global/per-message language controls and passing UI/live tests. Language limitations below describe the earlier implementation stage.

# IP-SAKTI implementation and verification report

Report generated: 2026-09-19T04:30:33.460899+00:00

The existing app was extended into a citation-grounded domain MVP. Full problem-statement coverage and production certification are not complete.

## Existing architecture and data

Streamlit owns the interface and local JSON conversation history. Upload loaders handle PDF, DOCX, PPTX, Excel, CSV, text, Markdown, HTML, JSON and XML. Recursive character splitting uses size 1,000 and overlap 200. CPU MiniLM normalized embeddings feed persistent Chroma. The existing Ollama Cloud model is gpt-oss:120b. Previously, unfiltered top-5 similarity retrieval and an explicit general-knowledge fallback could produce unsupported answers. There are no separate REST API endpoints.

The inspected domain dataset had 26 registry entries, nine processed document records and 3,478 chunk records. There were 86 duplicate chunk texts and one duplicate full-text record. Stored vectors were 1,024-dimensional BGE-M3 according to the dataset README, incompatible with the existing 384-dimensional collection. Several supposed full texts were navigation or article-title lists. Chunk sizes ranged from 7 to 98,107 characters. PDF page metadata was missing from the processed dataset. The ingestion scripts mentioned by its README were absent.

This is a factual legal corpus, not a supervised training set. RAG and source refresh are appropriate; no LLM training or fine-tuning was performed. Existing dataset metadata includes jurisdiction, regime, organization, source URL and legal-unit fields. Missing legal-unit labels and unverified dates were not filled with invented values. Sources include English and Hindi material.

Existing uploads are an AI PDF, an ML slide deck and Cars.xlsx. Cars.xlsx has 303 rows on its populated sheet, 13 columns, 325 missing cells and 14 duplicate rows; its second sheet is empty. These files are not Ayurveda legal authority and remain in uploaded-document mode. The slide deck has 15 slides. The AI PDF has 11 pages, three without extractable text. Before migration the original collection had 95 chunks, including stale references to absent files; absent upload files are excluded from retrieval.

## Requirement mapping

Target users: Ayurveda practitioners, researchers, AYUSH startups/MSMEs and cultivators. The MVP provides India/international jurisdiction selection, routing across IP types and regulatory questions, formulation/ABS clarification, source-aware retrieval, supported partial answers, multilingual answer selection, source citations and facilitator/database pointers. Statutes, rules, treaty and official-regulator evidence are kept distinct from user uploads.

## Implementation

- Added a separate curated collection inside the existing Chroma database. Both collections retain MiniLM; original incompatible vector files are preserved but not imported.
- Reparsed usable originals with PDF pages. Added controlled PDF acquisition and Crawl4AI web extraction, validated source manifest, content hashes, incremental ingestion and corpus snapshots.
- Added BM25/semantic retrieval, IP-type routing, jurisdiction filtering, selected-upload filtering and multi-regime candidate selection.
- Removed the general-knowledge fallback. Generated claims select real source passages; a second model call checks entailment. Unsupported claims are dropped or the answer abstains. This reduces risk but is not a proof of legal accuracy.
- Preserved conversation history, bookmarks, uploads and exports. PDF export is now on demand and browser-path configurable. Response transformations reuse evidence within the same source/jurisdiction scope.
- Added fixed legal-information notice, local-provider privacy notice, bounded uploads and localhost binding. No subscription access, legal filings or messages to third parties occur.

## Files

Modified: app.py, config.py, requirements.txt, embeddings/embedding_model.py, vectordb/chroma_manager.py, rag/retriever.py, rag/chatbot.py, utils/document_tracker.py, utils/smart_chat.py.

Added: ingestion/{__init__,pipeline,acquire}.py; evaluation/{__init__,run,check_storage,report}.py and questions/results JSON; tests/{__init__,test_grounding}.py; README.md; this report; .env.example; .gitignore; .streamlit/config.toml; requirements-acquisition.txt; curated source manifest, acquired originals, corpus snapshots and local ingestion state.

Intentionally preserved: the existing Ollama secret in .env (BHASHINI credentials were added separately); original dataset registry/processed documents/chunks/embeddings; original uploaded document contents; document loaders and splitter; existing framework, LLM and embedding model. Local virtual environment and model cache were created for testing.

## Actual validation

- Live evaluation cases recorded: 17; runtime errors: 0.
- Expected-source questions: 14; source hit@8: 14/14.
- Expected-source questions producing answers: 14/14. Remaining cases abstained; these are not counted as accurate answers.
- Unsupported-request abstentions: 3/3.
- Jurisdiction checks passing: 17/17.
- All 17 grounding and BHASHINI unit tests passed, including translated-claim rejection, API failure redaction, malformed translation responses and script routing. The original 25 Python files passed syntax parsing; subsequently changed app, chatbot, BHASHINI client and test files also passed.
- pip check reported no broken requirements. The Streamlit process was started on 127.0.0.1:8501.
- The automated Streamlit AppTest command was rejected at approval; it was not rerun through another tool. UI interactions and PDF export remain unverified.

Storage verification: `{"curated_chunks": 3697, "curated_sources": 22, "repeat_ingestion_pass": true, "repeat_upload_count_after": 95, "repeat_upload_count_before": 95, "selected_upload_count": 1, "selected_upload_filter_pass": true, "source_metadata_pass": true}`

## BHASHINI Udyat integration

Added utils/bhashini.py and tests/test_bhashini.py. Configured credentials in ignored .env; preserved the existing Ollama key. The official Dhruva inference endpoint authenticated successfully for English/Hindi/Tamil translations. The Udyat key is stored separately and is not sent as the inference Authorization header.

A sidebar toggle enables Hindi/Tamil query translation before retrieval and claim translation before the final evidence audit. Source passages and citations are unchanged. HTTP redirects are refused and remote error bodies are never displayed. English/Tanglish retain the Ollama path. Fixed notices remain English. Speech is not implemented.

Additional live RAG checks passed: 4/4 (Tamil and Hindi cited answers, English regression, unavailable TKDL abstention). Results: evaluation/bhashini_live_results.json. Passing checks do not establish translation or legal accuracy.

Streamlit was restarted to load the credentials and sidebar control. UI interaction tests remain unverified following the earlier declined approval.

Observed live latency: median 7.20s, maximum 33.22s. This includes local retrieval and cloud calls, not a controlled production benchmark.

These development questions are not a held-out evaluation. Source hit@8 is not answer accuracy, and passing model entailment checks is not independently measured faithfulness. No 100% accuracy claim is made.

| Test question | Result | Sources |
|---|---|---|
| Under Section 3(p), can traditional knowledge itself be patented in India? | cited answer | patent_rule_24b, patents_3 |
| What is the request-for-examination time limit under Rule 24B, and what is the exception for applications filed before the 2024 amendment? | cited answer | patent_rule_24b |
| What does section 3(a) say about Ayurvedic, Siddha or Unani drugs? | cited answer | cdsco_drugs_cosmetics_act_1940 |
| Who can apply for registration of a geographical indication under section 11? | cited answer | ip_india_gi_act |
| What does the Nagoya Protocol say about prior informed consent for access to genetic resources? | cited answer | nagoya_full, wto_trips_agreement |
| What disclosure does Article 3 of the WIPO GRATK Treaty require? | cited answer | gratk, wto_trips_agreement |
| Can a PCT application by itself give me a worldwide patent? | cited answer | wipo_pct_guide, wipo_pct_intro |
| What does the Madrid System protect? | cited answer | wipo_madrid_guide, wto_trips_agreement |
| How does the Hague System relate to industrial designs? | cited answer | wipo_hague_guide, wto_trips_agreement |
| What benefit-sharing provisions are in the 2025 ABS Regulations? | cited answer | abs_2025, bd_amendment_act_2023_gazette, nba_faq |
| Explain patent protection and benefit sharing for an Ayurvedic invention using Indian biological resources. | cited answer | abs_2025, nba_faq, patents_3 |
| Give me the secret TKDL record for my proprietary formulation. | abstained | cdsco_drugs_cosmetics_act_1940 |
| Who won the football match yesterday? | abstained |  |
| Guarantee that my unnamed herbal mixture is patentable and approved for sale. | abstained |  |
| பாரம்பரிய அறிவுக்கு இந்தியாவில் காப்புரிமை பெற முடியுமா? | cited answer | patents_3 |
| क्या भारत में पारंपरिक ज्ञान का पेटेंट हो सकता है? | cited answer | patents_3 |
| What is the purpose of the FSSAI order dated 25 July 2025 concerning category A Ayurveda Aahara? | cited answer | fssai_category_a_order |

## Source registry and acquisition results

Content validation is distinct from legal/current-version validation. Local snapshots may be historical. Unknown publication/effective dates remain unknown.

| Source | Jurisdiction | Status | Why included / source |
|---|---|---|---|
| Geographical Indications of Goods (Registration & Protection) Act, 1999 | india | verified | gi; [original](https://ipindia.gov.in/frontend/pdf/mannual/1_49_1_gi-act-1999.pdf) |
| Biological Diversity (Amendment) Act, 2023 | india | verified | biodiversity_abs; [original](https://egazette.gov.in/WriteReadData/2023/247815.pdf) |
| Drugs and Cosmetics Act, 1940 and Rules, 1945 (incl. Schedule E-1, relevant to Ayurveda classification) | india | verified | drug_regulation; [original](https://cdsco.gov.in/opencms/export/sites/CDSCO_WEB/Pdf-documents/acts_rules/2016DrugsandCosmeticsAct1940Rules1945.pdf) |
| Agreement on Trade-Related Aspects of Intellectual Property Rights (TRIPS), as amended by the 2005 Protocol | international | verified | trade_treaty; [original](https://www.wto.org/english/docs_e/legal_e/trips_e.htm) |
| Patents Act 1970 | india | unavailable | patents; [original](https://www.indiacode.nic.in/bitstream/123456789/1392/1/a197039.pdf) |
| Nagoya Protocol full text | international | verified | biodiversity_abs; [original](https://www.cbd.int/abs/doc/protocol/nagoya-protocol-en.pdf) |
| WIPO GRATK Treaty | international | verified | traditional_knowledge; [original](https://www.wipo.int/wipolex/en/text/592504) |
| Biological Diversity ABS Regulations 2025 | india | verified | biodiversity_abs; [original](https://www.nbaindia.nic.in/sites/default/files/2026-07/GNABSREG_2025.pdf) |
| Ayurveda Aahara Regulations 2022 | india | unavailable | food_regulation; [original](https://www.fssai.gov.in/upload/notifications/2022/05/62789a20b54bdGazette_Notification_Ayurveda_Aahara_09_05_2022.pdf) |
| NBA official frequently asked questions | india | verified | biodiversity_abs; [original](https://nbaindia.nic.in/about-us/faqs) |
| Patents Act: inventions not patentable | india | verified | patents; [original](https://ipindia.gov.in/acts/patent-act-1970/section-3) |
| Patents Rules: examination of application (Rule 24B) | india | verified | patents; [original](https://ipindia.gov.in/acts/patent-rules-2003/rule-24b) |
| PCT international patent system | international | verified | patents; [original](https://www.wipo.int/en/web/pct-system) |
| Madrid international trademark system | international | verified | trademarks; [original](https://www.wipo.int/en/web/madrid-system) |
| Hague international design system | international | verified | designs; [original](https://www.wipo.int/en/web/hague-system) |
| WIPO trade secrets overview | international | verified | trade_secrets; [original](https://www.wipo.int/en/web/trade-secrets) |
| Protection of Plant Varieties and Farmers' Rights Act 2001 | india | verified | plant_variety; [original](https://plantauthority.gov.in/sites/default/files/ppvfract2001.pdf) |
| EMA herbal medicinal products | international | verified | export_eu; [original](https://www.ema.europa.eu/en/human-regulatory-overview/herbal-medicinal-products) |
| FDA botanical drug development | international | unavailable | export_us; [original](https://www.fda.gov/drugs/cder-small-business-industry-assistance-sbia/botanical-drug-development-guidance-industry) |
| WIPO Budapest microorganism deposit system | international | verified | patents; [original](https://www.wipo.int/en/web/budapest-system) |
| Designs Act 2000 | india | verified | designs; [original](https://www.wipo.int/wipolex/en/text/594125) |
| Copyright Act 1957: WIPO Lex source version | india | verified | copyright; [original](https://www.wipo.int/wipolex/en/legislation/details/22949) |
| Trade Marks Act 1999 (amended through 2023) | india | verified | trademarks; [original](https://www.wipo.int/wipolex/en/legislation/details/22958) |
| WIPO: Introduction to the PCT | international | verified | patents; [original](https://www.wipo.int/en/web/pct-system/introduction) |
| FSSAI order dated 25 July 2025: Ayurveda Aahara category A | india | verified | food_regulation; [original](https://www.fssai.gov.in/upload/uploadfiles/files/Order%20dated%2025-07-2025%20enclosing%20Ayurveda%20Aahara.pdf) |

Unavailable sources and exact recorded errors:

- patents_act: 404 Client Error: Not Found for url: https://www.indiacode.nic.in/bitstream/123456789/1392/1/a197039.pdf
- ayurveda_aahara: Expected PDF, received portal/HTML
- fda_botanical: 404 Client Error: Not Found for url: https://www.fda.gov/apology_objects/abuse-detection-apology.html

## Remaining limitations and next steps

The corpus is not an exhaustive current consolidation. Full Ayurveda Aahara regulations, all 2024 patent/biodiversity rule changes, current advertising/labelling/cosmetic/phytopharmaceutical law, pharmacopoeial standards, case law, treaty membership status and all export markets require further primary-source acquisition and review. Some regulator pages are unavailable or return portal HTML. Use the manifest to retry specific sources or ingest an officially downloaded original with its provenance. Do not treat overview pages as the complete legislation.

The app is a trusted single-user MVP, not a multi-tenant deployment. Authentication, encryption, retention management, comprehensive audit/consent administration, DPDP/AI-standard assessment, voice input/output, knowledge graphs, agentic orchestration and paid-source connectors are not implemented. The problem statement permits staged delivery; these are not silently represented as complete.

Run commands, exact environment-variable names, acquisition setup and refresh instructions are in README.md. The next UI validation step is an approved end-to-end test of jurisdiction selection, upload, conversation switching, translations and exports. No further UI test was attempted after approval was declined.
