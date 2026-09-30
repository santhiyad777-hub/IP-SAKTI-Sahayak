# Security implementation and validation — 28 September 2026

The workspace now requires account registration/sign-in before loading conversations or private files. No default accounts were created. Open http://127.0.0.1:8502, choose **Create account**, acknowledge provider processing, and use a unique passphrase of at least 15 characters. Then sign in.

## Delivered

- SQLite account store with scrypt password hashing, persistent attempt limits and hashed server-side session tokens.
- Session expiry, logout, logout-all and password change with session revocation.
- Owner-scoped chat read/write/delete, optimistic concurrency and history quotas.
- Account-specific uploads, vector databases, preferences, bookmarks, briefs, translations, audit and exports. Identical filenames in two accounts remain separate.
- Filename/signature/ZIP/XML screening, upload quotas, serialized per-account changes, bounded parser subprocesses and rollback on upload failures.
- Private downloads embedded in the authenticated page instead of shared media URLs. External Markdown images do not automatically load.
- CORS/XSRF protection, disabled static serving/telemetry/error details, explicit HTTPS deployment configuration, and disabled source watching to avoid optional Transformer module scans.
- Updated affected runtime packages; removed unused LangChain community/agent packages.
- Dockerfile, Render blueprint, Railway configuration and portable public-only corpus seed. Neither existing chats nor secrets are included in the image build context.

## Verified

| Check | Result |
|---|---|
| Automated regression/security/UI suite | 107 passed; zero failures/errors/skips |
| Real browser registration/login/logout/private download/second-user isolation | 9 checks passed |
| Public retrieval regression | 13/13 passed |
| Authenticated upload, parsing, repeated indexing, selected-file retrieval and delete | Passed |
| Public corpus readiness | 48 sources, 6,895 chunks; original files/hashes and metadata checked |
| Portable deployment seed install/restart | Passed; public-only rows and portable paths; no duplicate indexing |
| Installed dependency compatibility | `pip check`: no broken requirements |
| Published dependency advisory scan | 165 packages queried; zero lookup errors; **not clean**: Chroma has 8 advisory records |

Machine-readable results are in `evaluation/final_tests.json`, `evaluation/security_browser_results.json`, `evaluation/storage_results.json`, `evaluation/readiness_results.json`, `evaluation/deployment_seed_results.json`, `evaluation/dependency_security.json`, and `dataset/review_26045/retrieval_checks.json`.

Chroma advisories concern its HTTP server's model configuration and authorization. This application uses separate embedded/local databases and never exposes a Chroma HTTP server or user-selected model repositories. The remaining findings and mitigation are documented in SECURITY.md; they are not concealed or represented as fixed upstream.

## Deployment boundaries

See DEPLOYMENT.md for Render/Railway steps, required HTTPS origin, API secrets and persistent-volume paths. Use one replica with the present SQLite/Chroma architecture. This workstation has no Docker engine, so the Linux image build, PDF renderer and actual cloud deployment remain unverified on the target platform. No Render/Railway service was published.

Old shared conversations, preferences and uploads remain on the developer machine and were deliberately not assigned to any new account. They are excluded from deployment. Server administrators can access stored content; application-level encryption, verified self-service account recovery, MFA, automatic retention and formal privacy/security certification are not supplied. This change does not certify legal answer accuracy or 100% SIH completion/security. Independent security and domain review remain required before confidential production use.
