# SIH26045 dataset review ? 28 September 2026

## Scope and conclusion

Reviewed against the supplied Ministry of Ayush / AIIA problem statement for IP-SAKTI Sahayak. The unrelated SIH problem statements pasted around entry 26045 were excluded from scope.

The existing corpus did not contain all required evidence. This review adds official originals, replaces unsupported local summaries, and removes unrelated demo upload records. It does **not** certify exhaustive legal coverage or current consolidated law across all jurisdictions.

## Completed update

- 19 new official sources added; 5 local summaries replaced by official originals.
- 48 active sources and 6,895 indexed chunks after cleanup.
- All 95 unrelated/stale upload chunks removed; upload collection is empty.
- 3,694 old-machine source paths repaired.
- 13/13 real retrieval checks pass, including India/international separation and source metadata.
- 15/15 extraction, routing and existing grounding unit tests pass.
- File hashes, required metadata, nonempty text, source file paths, source-count alignment and SQLite quick-check pass.
- Six former summaries are retained only in `quarantined_summaries/`; the active corpus excludes them.

## Coverage matrix

| Problem-statement requirement | Evidence retained or added | Remaining limits |
|---|---|---|
| Indian patents and 2024 rules | Existing Patents Act and Rules snapshots, Section 3, Rule 24B; original CGPDTM TK examination guidelines replace a local summary | Check amendments after each snapshot and live forms/fees |
| GI, trademarks, designs, copyright, plant varieties, trade secrets | Existing Acts and WIPO guidance; Navara Rice GI application 17 public registry record added | Representative registry record only; not a complete patent/trademark/GI register; Indian trade-secret case law remains limited |
| Biodiversity and ABS | Consolidated Biological Diversity Act through 2023, 2024 Rules, 2025 Amendment Rules, existing 2025 ABS regulations and NBA FAQ | Rules must be read together; original notification versus consolidated text distinguished |
| Classical/proprietary drugs, phytopharmaceuticals, cosmetics | Existing Drugs & Cosmetics Act/Rules; full NDCT Rules 2019 and Cosmetics Rules 2020 added | Existing Drugs & Cosmetics snapshot is from 2016; a full amendment-by-amendment update is still required |
| Ayurveda Aahara, nutraceuticals, labelling, advertising | Original FSSAI Ayurveda Aahara 2022, nutraceuticals 2016, labelling 2020, advertising/claims 2018 notifications; existing 2025 category-A order | Base notifications are not current compilations. June 2026 additional Aahara recipes and later food-law amendments are not yet fully captured |
| Drug advertising and case law | Official Drugs and Magic Remedies Act; Supreme Court In Re Patanjali Ayurved Ltd, 2024 INSC 605 | One representative judgment does not cover all subsequent orders or advertising case law |
| CBD, Nagoya, GRATK, TRIPS | Full CBD added; existing treaty originals retained | Treaty adoption/ratification/entry-into-force and country participation need live checks |
| PCT, Madrid, Hague, Budapest | Full treaty/Act/protocol texts added alongside existing guides | Current procedural regulations, fees, and contracting-party status can change separately |
| Export market access | Original FDA Botanical Drug Development guidance, existing EMA overview, UK MHRA THR guidance | USA/EU/UK introductory coverage only; not all export markets or ingredient-specific restrictions |
| TKDL / prior-art pointer | Actual CSIR public TKDL information replaces local summary; original CGPDTM guidelines | No restricted TKDL formulation records or paid databases accessed |
| Pharmacopoeial standards and authoritative formularies | Official PCIMH access/catalogue references identified below | **Gap:** full standards/monographs not imported; PCIMH connection/certificate errors and some paid access requirements |
| DPDP / privacy | Original DPDP Act 2023 and notified Rules 2025 added | Phased commencement applies; dataset additions do not implement application compliance |
| Recognised AI-application standards | NIST AI RMF 1.0 official original added as an international voluntary framework | Downloading a framework does not implement controls or establish certification |
| Multilingual answers, confidence, escalation, graph, voice, paid connectors | Corpus supports the existing application; jurisdiction metadata retained | These are application capabilities, not satisfied merely by downloading documents; no claim of full feature completion |

## Removed or replaced

- Out-of-scope demo embeddings for Cars.xlsx, ML PPT.pptx, artificial-intelligence material, a CV, and test text; stale upload rows with no source file are removed as well.
- Six locally written `content.txt` summaries (TK examination, TKDL, Biodiversity Rules 2004, Aahara, drug advertising, FDA botanicals) are excluded or replaced by retrieved official originals.
- The obsolete Biodiversity Rules 2004 summary is excluded from active answers. The [WIPO 2024 Rules record](https://www.wipo.int/wipolex/en/legislation/details/23135) identifies the supersession and links the 2025 amendment.
- Two unavailable alias entries (`ayurveda_aahara`, `fda_botanical`) are removed from the active manifest; the original documents use the canonical source IDs.
- Imported old-machine paths are repaired. WTO TRIPS metadata now identifies the existing HTML source correctly.

Relevant original statutes and historical source snapshots are retained. Identical wording on different statutory pages is not automatically deleted, because page-specific citations matter. Previous database and manifest state is retained under `before_update/` for rollback and is never queried by the application.

## Known acquisition/access gaps

- [PCIMH official standards FAQ](https://www.portal.pcimh.gov.in/content/faqs): timed out, including retry outside the restricted network.
- [PCIMH API Part-I amendment 2025](https://pcimh.gov.in/WriteReadData/RTF1984/APIpart1.pdf): certificate-chain verification failed. TLS verification was not disabled.
- [PCIMH official publication catalogue](https://www.portal.pcimh.gov.in/products?categories=9b36e0a5-5788-4ade-95d3-8c4fdd0e3687): some full publications require purchase. No purchase or subscription was attempted.
- India Code drug-advertising downloads timed out; an official Assam AYUSH copy was acquired instead.
- FSSAI's old download path returned HTML. Original notifications were successfully retrieved from the official FSSAI legacy host, with PDF signatures and text patterns checked.

## Validation and reproducibility

Exact source/chunk totals, source-hash checks, metadata/path checks, and retrieval smoke-test results are written to `verification.json` and `retrieval_checks.json`. Retrieval checks do not call an LLM or prove generated-answer legal accuracy. The acquisition candidate list and scripts remain in the project so failures and provenance can be reviewed.
