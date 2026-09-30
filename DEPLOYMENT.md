# Deployment: Render or Railway

Use the directory containing `Dockerfile`, `app.py` and `render.yaml` as the repository/service root. Do not upload the parent Downloads folder. The Docker build uses an explicit code/public-corpus allowlist; `.env`, existing chats, private databases and uploads are excluded.

## Render

1. Create a private repository containing this project and connect a Render Blueprint using `render.yaml`.
2. The blueprint requests one Docker web service and a 10 GB disk mounted at `/var/data`. Use a paid service with enough memory; start with at least 2 GB and measure actual usage. The local embedding model plus concurrent password hashing can exceed small free-tier memory limits.
3. Set `PUBLIC_BASE_URL` to the exact HTTPS origin, for example `https://your-service.onrender.com`. Set `OLLAMA_API_KEY` in Render's secret environment controls. Do not commit keys. The launcher refuses to start without a valid HTTPS origin.
4. Keep `APP_DATA_DIR=/var/data/ip-sakti`. Add optional Bhashini variables listed in `.env.example` if translations are needed. The app listens on the platform's `PORT` and exposes `/_stcore/health`.
5. Deploy one instance. Open the HTTPS site, create two test accounts, and verify isolation before sharing the URL. Restart the service and confirm both accounts and their own histories survive.

## Railway

1. Create a project/service from this project's private repository. `railway.json` selects the Dockerfile and health check.
2. Attach a persistent volume at `/data`. Set `APP_DATA_DIR=/data/ip-sakti`. A volume is required: an ephemeral filesystem would lose accounts, chats and documents on redeploy.
3. Generate a public HTTPS domain. Set `PUBLIC_BASE_URL` to that origin. Set `OLLAMA_API_KEY`, `OLLAMA_HOST=https://ollama.com`, and `LLM_MODEL=gpt-oss:120b`. Add optional Bhashini secrets if used.
4. Keep one replica, allocate at least 2 GB RAM initially, and deploy. Repeat the two-account and restart-persistence checks above.

The container entrypoint briefly starts with privileges to set ownership on the mounted application directory; it then runs the web process and parsers as UID/GID 10001. It does not recursively change ownership outside that directory. Use the documented mount paths.

## What is persistent

`APP_DATA_DIR/accounts.sqlite3` stores salted password hashes, hashed session tokens and owner-scoped conversations. `APP_DATA_DIR/users/<account-id>/` holds that account's uploads, private vector database, preferences and audit. `APP_DATA_DIR/public_indexes/<corpus-hash>/` contains only the public corpus. Public indexes are versioned so corpus updates do not overwrite private data.

The checked-in `deploy_assets` bundle contains 48 reviewed public sources and 6,895 chunks, with precomputed embeddings and a SHA-256 checksum. Deployment does not copy the legacy shared Chroma database. Rebuild the public seed after administrator-reviewed corpus changes:

```powershell
.\.venv\Scripts\python.exe -m evaluation.export_public_seed
```

The build downloads the fixed public embedding model. Runtime API access to the configured Ollama/Bhashini providers is required for answers/translations. A health check only establishes that the UI server responds; it does not verify provider credit or legal accuracy.

## Operations before public access

- Keep exactly one instance with this SQLite/local-Chroma design. Multi-replica operation requires a shared database, central rate limits and private object/vector storage, and is not implemented here.
- Enable platform backups, restrict dashboard/SSH access and use MFA for operator accounts. Stop the service before a whole-volume backup/restore so SQLite WAL and Chroma files stay consistent. Store backups encrypted and test a restore to a separate service. Revoke all sessions after restoring a backup.
- Set edge rate limits/WAF and resource/budget alerts. Application limits do not replace protection from distributed denial of service or account-creation abuse.
- Use HTTPS only. Do not disable Streamlit CORS/XSRF protection or static-serving restrictions. Do not publish `private_data`, volume snapshots, `.env` or legacy backups.
- Repeat dependency auditing after building on Linux; local Windows checks do not assess base-image OS packages. Rebuild for security updates and perform an independent penetration test before handling valuable confidential submissions.
- The Linux image includes WeasyPrint and Noto fonts for PDF export, with external resource fetching disabled. Windows uses an installed Chrome/Chromium renderer. Validate Tamil/Hindi PDF output on the target image.

## Validation limits

The application is tested locally. This workstation does not have Docker available, so a Linux image build and actual Render/Railway deployment must be verified on the target platform. No cloud account or deployment was created by this change. This is not a claim of 100% security or legal correctness.

Official platform references: [Render disks](https://render.com/docs/disks), [Render Docker services](https://render.com/docs/docker), [Railway volumes](https://docs.railway.com/volumes), [Railway Dockerfiles](https://docs.railway.com/builds/dockerfiles).
