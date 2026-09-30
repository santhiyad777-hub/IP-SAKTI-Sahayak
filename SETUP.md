# Local setup and verification

Use Python 3.11 and the project `.venv`; do not use system Python for deployment.
The existing `.venv` was checked with `pip check` and has no broken requirements.

Start from this directory:

```powershell
.\Start-IPSAKTI.ps1
```

The server binds to 127.0.0.1:8502. For a different local port:

```powershell
.\Start-IPSAKTI.ps1 -Port 8503
```

Fresh installation (network and disk space required):

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-cache-dir torch==2.14.0 --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements.txt
.\.venv\Scripts\python.exe -m pip install jsonschema==4.26.0
```

Configure `.env` using `.env.example`. Never commit credentials. Ollama requires a working key and provider access. Bhashini is optional; its configured translation path is tried with existing fallback behavior. An installed Chrome/Edge or CHROME_PATH is needed for PDF export.

Verification (no AI calls):

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe -m evaluation.readiness
.\.venv\Scripts\python.exe -m evaluation.check_storage
.\.venv\Scripts\python.exe -m evaluation.reviewed_corpus
```

Storage verification temporarily indexes a unique synthetic text fixture and deletes only that fixture afterwards. Readiness hashes the local originals and checks manifest/index coverage. None of these checks certifies legal accuracy.

Optional live generation checks send test questions and source excerpts to the configured provider:

```powershell
.\.venv\Scripts\python.exe -m evaluation.verify_accuracy
```

A missing model cache may require a first embedding-model download. Existing local weights and vector data are present in this workspace. Source refresh remains a reviewed maintenance operation; see README ingestion instructions. Local development stays on localhost. Registration/sign-in and per-account isolation are implemented; create an account before entering the workspace. Legacy shared chats are intentionally not imported. See SECURITY.md for limits and DEPLOYMENT.md for Render/Railway setup. No security certification is claimed.

The Streamlit source watcher is disabled to avoid lazy Transformer-module import errors and unnecessary production scanning. Restart the local server after changing Python files.
