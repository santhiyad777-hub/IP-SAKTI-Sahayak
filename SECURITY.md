# Account security and data isolation

Registration/sign-in are required before the app loads private content. There are no default accounts and no production authentication bypass. Users choose a unique username and a passphrase of 15–128 characters. No email is collected, so username registration does not prove a real-world identity and email-based password recovery is not available.

## Implemented controls

- Passwords: unique random salts and scrypt (N=2^17, r=8, p=1); constant-time digest comparison. Only password hashes are stored. Concurrent hashing is bounded to control memory use.
- Sessions: cryptographically random opaque tokens retained in server-side Streamlit session state, with only token hashes in SQLite. Idle expiry is 30 minutes; absolute expiry is 12 hours. Logout revokes the current session; logout-all and password changes revoke all sessions for that account. A browser refresh can require sign-in again. No token is placed in a URL or browser local storage.
- Owner authorization: every conversation read/write/delete uses the authenticated account. Knowing a conversation ID grants no access. Optimistic revisions prevent a stale tab overwriting or resurrecting a deleted chat.
- Private storage: each account has separate upload paths and a physically separate Chroma database. Retrieval also checks owner metadata. Public curated sources are separate and read-only from the user UI. Bookmarks, product briefs and translated answers remain inside their owner's conversation.
- Message rendering: model-authored Markdown images are neutralized to prevent automatic external tracking requests; normal citation links remain available.
- Exports: private TXT/Markdown/JSON/PDF bytes are embedded in the authenticated page as downloads, avoiding Streamlit's shared media URLs. Logout clears all workspace state and translation/answer caches. Already downloaded copies cannot be revoked.
- Input handling: upload filenames reject traversal, Windows device names and alternate data streams. File extensions, PDF/Office signatures, ZIP expansion ratios and XML entity declarations are checked. Limits: 25 MB per file, 50 files/100 MB per account; parser process timeout 45 seconds; Linux CPU/memory/output limits; parsed text/chunk caps and a 10,000-chunk private index quota. Parser processes receive no provider credentials. This is resource isolation, not a hardened malware sandbox.
- Abuse controls: persistent registration/login/password-change rate limits, per-account question limits, bounded question and conversation sizes, with a 50 MB history quota per account. Do not rely on IP rate limits alone behind a proxy. Use platform edge controls as well.
- Deployment: CORS and XSRF protections enabled, static serving disabled, detailed browser errors and usage telemetry disabled; production launcher requires an HTTPS origin. API keys belong only in server/platform secret settings.

Password storage parameters follow the [OWASP password storage guidance](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).

## Data and privacy boundaries

This protects one signed-in user's content from another through the application. It is not end-to-end encryption. The service operator and anyone with privileged disk/database access can read stored chats and uploads. Use encrypted platform volumes/backups and restrict administrative access. Questions and retrieved excerpts go to the configured AI provider; translation may use Bhashini. The registration notice discloses this processing.

Legacy `knowledge_base/conversations.json`, old preferences and old shared uploads are deliberately not assigned to any new account. They remain unchanged on the developer workstation and are excluded from the deployment image. Migrate only after separately verifying ownership; never assign everything to the first registrant.

Existing conversation and document delete controls remove active data for that account. Backups, provider retention and files already downloaded by the user are separate. Automatic retention, verified account recovery, account-deletion workflows, MFA/SSO and formal compliance certification are not implemented.

## Operator recovery

There is no public password-reset endpoint. Do not reset an account solely because someone supplies its username. First verify ownership using a separately established process. A trusted operator can use `python -m security.admin revoke-all` to revoke restored/stolen sessions, or `python -m security.admin reset-password USERNAME` after ownership verification; the password is entered without echo and never passed on the command line. Operations use the same `APP_DATA_DIR` as the deployed app.

## Validation

The security regression suite covers cross-account reads/writes/deletes, private retrieval with identical filenames, stale edits, session expiry/revocation, password changes, rate limits, path traversal, malformed uploads, legacy isolation and the authentication UI. See `evaluation/final_tests.json`, `evaluation/storage_results.json` and `evaluation/security_browser_results.json` for actual results. Automated tests are not an independent penetration test or a guarantee of absolute security.

## Dependency review

The initial installed-version scan found published advisories in 13 packages. Affected maintained dependencies were upgraded and unnecessary LangChain community/agent packages removed; use the final `evaluation/dependency_security.json` rather than the initial count to assess the resulting environment.

Chroma's published advisories include GHSA-f4j7-r4q5-qw2c, GHSA-2wm9-hf6c-p5cr, GHSA-36p7-vc44-83pf and GHSA-xph7-9rjv-w5fr (plus duplicate PYSEC records). These concern the Chroma HTTP server's model configuration or tenant authorization. This app runs only embedded `PersistentClient`/local Chroma stores: it never starts `chroma run`, accepts remote Chroma API clients, enables RBAC providers, or accepts user-selected embedding repositories. Each user's private database is physically separate; the embedding model is operator-fixed with `trust_remote_code=False`. This reduces exposure to those reported server attack paths; it is not a claim that the dependency has no vulnerabilities. Do not expose a Chroma server without resolving its advisories and separately assessing authorization.

The version audit queries PyPI's published vulnerability data. It is not a source-code audit, exploitability proof, supply-chain attestation or OS-image scan. Any package lookup error must be treated as incomplete coverage. Linux image dependencies need their own post-build audit.

Final installed-version scan: 165 packages checked, no lookup errors. Chroma 1.5.9 remains flagged by 8 advisory records (4 GHSA issues plus duplicate PYSEC entries); the other 164 packages had no reported records in this scan. The dependency scan is explicitly not marked clean. Its command exits nonzero when findings or lookup errors remain. Review the local-only Chroma mitigation above before release.
