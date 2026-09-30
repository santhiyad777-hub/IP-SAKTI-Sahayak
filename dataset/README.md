# IP-SAKTI Sahayak corpus (SIH26045)

The active source manifest is `source_registry/curated.json`. The application indexes only its verified sources into Chroma collection `ip_sakti_v1` using the configured MiniLM embedding model (384 dimensions).

`source_registry/registry.json`, `processed/`, and earlier `corpus_versions/` are historical pipeline artifacts, not the active corpus. In particular, the old processed BGE-M3 vectors must not be loaded into the current MiniLM collection.

## Review and provenance

See `review_26045/COVERAGE_REPORT.md` for problem-statement coverage, acquisition failures, and remaining gaps. `review_26045/acquisition.json` records downloaded originals, source URLs, hashes, and extraction checks. `review_26045/verification.json` records the post-update database audit.

- Raw PDFs are retained byte-for-byte. Website bodies are extracted without paraphrasing, with original HTML retained for new acquisitions.
- Some bilingual PDFs are indexed from the English portion because the legacy-font Hindi extraction is corrupt. `page_start` is zero-based and preserves original PDF citation page numbers. `first_page_marker` removes preceding non-English text on a shared first page.
- Download success and pattern validation establish provenance and readability, not that every statute is a current consolidation. Version metadata identifies snapshots; later amendments and commencement dates still require checking.
- Former locally written summaries are quarantined and excluded from retrieval. Historical 2004 biodiversity rules must not be treated as the current filing procedure.
- Restricted TKDL records and paid pharmacopoeial content have not been downloaded.

## Updating

Run from the project root:

```
python -m ingestion.review_corpus --fetch
python -m ingestion.pipeline
```

The first command stages only the explicitly reviewed candidates in `review_26045/candidates.json`; it does not automatically approve them or change the active manifest. Review and add verified entries to `curated.json` before ingestion. Existing curated sources can also be refreshed with `python -m ingestion.acquire --refresh --ingest`.

The one-time migration scripts `ingestion/apply_review_26045.py` and `ingestion/finalize_review_26045.py` document this review. They are not a scheduled updater. `review_26045/before_update/` is a rollback backup, never an active ingestion source.
