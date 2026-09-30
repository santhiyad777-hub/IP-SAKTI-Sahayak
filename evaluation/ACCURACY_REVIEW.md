# Accuracy review ? 2026-09-28

Changes: unique PDF pages are selected before the retrieval limit; empty page extraction no longer overwrites evidence; ambiguous filename fallback fails closed; GI registry questions route to GI sources; patent-formulation questions no longer force drug-regulation evidence. Query translation preserves the requested jurisdiction and subject.

Generation now checks whether the supported claims answer the main question. A correctable audit failure gets one revision against the same evidence, followed by a fresh audit. Background-only answers are rejected. Separate deterministic checks detect front-of-pack scope expansion, importing efficacy into Section 3(e) without supporting evidence, and broadening Section 3(p) to everything based on traditional knowledge. These checks supplement, not replace, source review.

Live examples are recorded in accuracy_verified_answers.json. Earlier diagnostic traces are retained and can contain rejected or superseded outputs. They are not curated legal knowledge.

Limits: the generator and semantic auditor use the same model and may share errors. Passing citation checks does not prove legal correctness. The database is a snapshot and not a live legal-update service. Requirements can depend on product facts, amendments, exceptions and destination country. The live review found overstatements despite successful semantic auditing; therefore no overall accuracy percentage or perfect-accuracy claim is warranted. The new deterministic rules address observed patterns, not every possible legal error. India and International remain separate user-selected scopes; select International for the treaty-wide Budapest benefit.

Primary-source spot checks: official Navara GI application 17 confirms its registration fields; WIPO Budapest summary confirms recognition of a deposit at an international depositary authority across contracting states. The Aahara Gazette pages 16?17 distinguish front-of-pack wording/logo from other label requirements.

Validation: 63 automated tests passed; all 13 retrieval checks found expected sources with jurisdiction separation and citations. Four live question outputs are saved. The final patent output corrected the Section 3(e) efficacy conflation, but its extra discussion still makes broad statements about claims based on traditional knowledge. That output must not be treated as a fully validated legal opinion. The labelling, GI and Budapest examples are useful spot checks, not proof that every requirement or exception is covered.
