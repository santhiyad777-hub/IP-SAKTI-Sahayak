# Multilingual implementation and verification

Verified: 2026-09-19T08:44:37.468702+00:00

Updated the existing Streamlit/Ollama/MiniLM/Chroma application. Auto, English, Tamil and Hindi are available; Tanglish is not an output option. The global selection controls interface text and new answers regardless of question language. Auto follows the question. Greetings are localized without searching legal documents.

Each assistant answer has a separate language selector. Original question, answer, language, retrieved context, source references and translated versions are stored in the existing conversation JSON with stable message and conversation IDs. A per-message override changes only that answer. Switching back restores the original version; translation does not perform another retrieval.

BHASHINI credentials use BHASHINI_UDYAT_KEY and BHASHINI_INFERENCE_KEY in ignored .env. Older names remain read-compatible. Translation protects identifiers and verifies unchanged URLs, numeric references and citations. A model equivalence check rejects meaning changes. BHASHINI has bounded retries and the configured Ollama translator provides fallback. Original document names, user-authored questions and source excerpts remain intact.

Validation: 44 tests passed, including 3 isolated Streamlit UI tests; 19/19 real-provider checks passed. The temporary official-document upload and its index entries were removed after testing. Server health: HTTP 200.

Central translations: utils/ui_strings.json. Shared conversation flow: rag/conversation.py. Version storage and reference checks: utils/message_versions.py. UI tests use temporary history and do not modify real conversations.

| Live check | Result |
|---|---|
| English selection / English question | PASS |
| Hindi selection / English question | PASS |
| Tamil selection / English question | PASS |
| Auto / English | PASS |
| Auto / Hindi | PASS |
| Auto / Tamil | PASS |
| Individual English-origin answer -> Tamil | PASS |
| Individual English-origin answer -> Hindi | PASS |
| Individual English-origin answer -> English | PASS |
| Original and neighboring messages retained | PASS |
| Tamil-origin answer -> English | PASS |
| Document upload / processing / embeddings / index | PASS |
| Uploaded document question / English | PASS |
| Uploaded document question / Tamil | PASS |
| Uploaded document question / Hindi | PASS |
| Temporary upload cleaned up | PASS |
| Unsupported question / English | PASS |
| Unsupported question / Tamil | PASS |
| Unsupported question / Hindi | PASS |

Artifacts: evaluation/multilingual_final_results.json; evaluation/multilingual_unit_results.json. Run instructions: README.md.

The UI tests verify Streamlit widget state and rendered message contents. Native browser styling and PDF printing were not separately automated. Passing tests is not a guarantee of perfect translation or legal accuracy. The original corpus coverage and production-deployment limitations still apply.
