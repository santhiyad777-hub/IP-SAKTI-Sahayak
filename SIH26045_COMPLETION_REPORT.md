# SIH26045 implementation and verification report

Date: 28 September 2026. Target: Ministry of Ayush, IP-SAKTI Sahayak.

## Result

The local, single-user MVP has additional working product-intake, provenance, expert-handoff and corpus-review tools. It is **not 100% complete or certified against the full SIH vision**. Software test results do not establish legal-answer accuracy. A tested product-classification scenario still abstains and needs further domain/retrieval review; this is a material limitation, not a completed classification evaluation.

## Added features

- **Product brief:** per-conversation facts covering use, route, claim, composition/text, novelty, resource origin, cultivated/wild status, applicant, activity and destination. Save without an API call. Classification and ABS actions use the existing grounded workflow. Unknown facts stay unknown.
- **Selective ABS intake:** asks for missing material facts, including cultivated/wild origin; does not treat a boilerplate reference to patentability as a request for patent advice. Clarification text is retained in the retrieval query.
- **Evidence Passport:** per-answer cited references, source text, original links, page, jurisdiction, version, acquisition date and available content hash; JSON export. Unresolved references and abstention have separate states. This is provenance, not calibrated confidence.
- **Source freshness:** jurisdiction-filtered local manifest view with search, file presence, download age and version notes. It never equates download age with current law.
- **Expert review pack:** downloadable original questions/answers, profile and citations for user-controlled human review; WIPO TISC navigation link. No automatic messages or appointments.
- **Privacy/audit:** clear provider/local-storage notice; local allowlisted audit events omit questions, answers, profile facts and credentials. Paid connectors remain disabled.
- English/Tamil/Hindi UI strings for the new tools. Removed source-mode selector stays removed.
- Isolated-environment launcher (`Start-IPSAKTI.ps1`), reproducible checks, setup and demo guide.

## Fixes

- Clear pending answer context when the active conversation is deleted.
- Show references actually cited in each answer instead of labelling every retrieval hit as a used source.
- Keep structured profile task separate from retrieval text and guard against unrelated patent-intake routing.
- Prefer category definitions for classification retrieval; preserve the added user clarification.
- Bound one retry when a draft returns only a redundant clarification; retain citation/audit rejection.
- Fix the storage evaluation's dependency on the removed Cars.xlsx file with a unique synthetic fixture and guaranteed cleanup path.
- Use current width arguments supported by the pinned Streamlit version.
- Avoid download-triggered reruns for new review exports.

## Verification artifacts

| Check | Evidence |
|---|---|
| Unit, grounding, multilingual UI, profile, audit and export tests | `evaluation/final_tests.json` and `final_tests.log` |
| Clean project dependencies | `.venv` pip check: no broken requirements; system Python has unrelated conflicts and is not the launch target |
| Active corpus/index and file integrity | `evaluation/readiness_results.json`: 48 active/indexed sources, 6,895 chunks; manifest hashes and citation metadata pass |
| Upload ingestion, repeat ingestion, selection and cleanup | `evaluation/storage_results.json`: all checks pass |
| 13 domain retrieval cases | `dataset/review_26045/retrieval_checks.json`; final run log `evaluation/final_retrieval_check.log` |
| Classification definition retrieval | `evaluation/classification_retrieval_results.json` |
| Desktop/mobile workflow | `evaluation/browser_workflow_results.json`: inventory rendered, review pack downloaded, no displayed exceptions or horizontal overflow |
| Live product smoke checks | `evaluation/sih_workflows_live_results.json`: classification abstention remains; ABS requests a missing source-origin fact |

Diagnostic traces are development artifacts and can include rejected or superseded answers. Do not ingest them as authority. Browser checks cover the inspected routes, not every browser/device combination.

## Requirement mapping and remaining work

| SIH requirement | Current state / boundary |
|---|---|
| India/international switch | Implemented; retrieval separation tested |
| Multilingual source-cited RAG | Implemented for English, Tamil and Hindi with Tanglish input; professional terminology review still needed |
| Minimum formulation clarification | Structured intake and chat clarification implemented; classification reliability remains incomplete |
| IP and regulatory routing | Existing routes and 48 sources; not exhaustive or guaranteed current-law coverage |
| ABS helper | Structured intake and routed evidence; not a compliance certificate or automatic exemption determination |
| TKDL/prior-art pointer | Public CSIR/TKDL sources; no restricted TKDL access or exhaustive prior-art search |
| Evidence/confidence indicator | Transparent evidence states; not a numerical legal-confidence probability |
| Human escalation | Review export + facilitator directory; no actual human review/appointment integration |
| Version-tracked maintained corpus | Hashes, versions, ingestion and freshness view; refresh is manual/reviewed, no scheduled legal-update certification |
| Pharmacopoeial standards / case law | Partial coverage; licensed standards and wider/current case-law coverage remain gaps |
| Privacy, audit and security | Registration/login, per-account SQL/file/vector isolation, session controls, upload limits, private exports and content-free events; no application encryption-at-rest or independent DPDP/AI-standard assessment |
| Paid subscriptions | Disabled; future connectors require explicit, logged permission and user entitlement |
| Relational legal knowledge graph / agents / voice | Not implemented as the full staged capabilities described in the statement |
| Accuracy evaluation | Software/retrieval/live checks exist; no independently reviewed held-out legal accuracy benchmark |

## Run and demonstrate

Use `Start-IPSAKTI.ps1` from this project directory. The app binds to http://127.0.0.1:8502 using `.venv`. See `SETUP.md` and `DEMO_GUIDE.md`. Open **Product brief & review tools** above the chat; open **Evidence passport** below a cited answer.

Account isolation and Render/Railway configuration are now implemented; target-platform build verification and independent security assessment remain required. See SECURITY.md and DEPLOYMENT.md. Before production or claiming full SIH compliance: resolve product classification coverage, obtain domain/legal review of answers and translations, maintain authoritative updates/licensed content, implement the remaining staged features and complete privacy/security assessment.
