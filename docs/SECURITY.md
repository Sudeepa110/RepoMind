# Security & Privacy Specifications

## Threat Model & Security Boundaries

RepoMind ingests untrusted third-party public GitHub repositories and processes their source code, comments, and documentation using deterministic parsers and an optional LLM. Every trust boundary enforces defense-in-depth controls.

---

### 1. GitHub URL Validation & SSRF Protection
Implemented in [validators.py](file:///d:/Repomind/backend/app/utils/validators.py):
- **Strict Host Allowlist**: Only `github.com` and `www.github.com` hostnames are accepted; arbitrary hosts, internal IPs (`127.0.0.1`, `10.*`, `192.168.*`), and cloud metadata IPs (`169.254.169.254`) are rejected.
- **Protocol Locking**: Only `https://` URLs are permitted (`http://`, `file://`, `ftp://`, `ssh://`, `git://` rejected).
- **Port & Credential Rejection**: Non-443 ports and embedded userinfo credentials (`user:pass@host`) are disallowed.
- **HTTP Redirect Inspection**: `_validate_redirect_host` inspects every HTTP redirect hop in `verify_github_repo_accessible` and rejects any redirect away from `github.com`, `www.github.com`, or `api.github.com` over HTTPS.
- **Git Protocol & Symlink Restriction**: [cloner.py](file:///d:/Repomind/backend/app/ingestion/cloner.py) executes `git clone` with `GIT_ALLOW_PROTOCOL=https`, `-c core.symlinks=false`, `-c submodule.recurse=false`, `GIT_TERMINAL_PROMPT=0`, and `GCM_INTERACTIVE=never`.

---

### 2. Zero Code Execution Guarantee
- **Static Text & AST Only**: Cloned code is inspected strictly as passive UTF-8 text and Tree-sitter syntax trees. RepoMind **never executes, imports, compiles, or evaluates** repository source code, build scripts, Dockerfiles, or package install hooks.
- **Isolated Workspaces**: Repositories are cloned into per-UUID directories under `storage/temp_repos/{repository_id}/` using shallow `depth=1 --single-branch --no-tags` clones.

---

### 3. Path Traversal & Secret File Exposure Prevention
- **Strict Containment (`is_relative_to`)**: File reads (`GET /api/v1/repositories/{id}/file`) normalize paths, reject `..` segments, resolve symlinks, and enforce `resolved_target.is_relative_to(resolved_workspace)` ([repositories.py](file:///d:/Repomind/backend/app/api/repositories.py)).
- **Sensitive Artifact Filtering**: Both the ingestion filter ([file_filter.py](file:///d:/Repomind/backend/app/ingestion/file_filter.py)) and the file viewer API explicitly deny access (HTTP `403`) to `.env`, `.env.*`, `*.pem`, `*.key`, `id_rsa`, `credentials.json`, `service_account.json`, `.git/`, `node_modules/`, and binary artifacts.

---

### 4. API Key Protection, CORS & Error Sanitization
- **No Frontend Secret Exposure**: `GEMINI_API_KEY` stays strictly on the backend process via environment variables. `/api/v1/health` exposes only a boolean `gemini_configured` status.
- **Environment-Driven CORS**: Allowed origins are configured via `CORS_ORIGINS` in [config.py](file:///d:/Repomind/backend/app/config.py).
- **Production Error Sanitization**: When `DEBUG=false` (`ENVIRONMENT=production`), `500 Internal Server Error` handlers return generic error messages rather than internal filesystem paths or stack traces.

---

### 5. Resource Exhaustion & Multi-Repository Isolation
- **Ingestion Quotas**: Enforces `MAX_REPO_SIZE_MB` (100 MB default), `MAX_INDEXED_FILES` (500), `MAX_FILE_SIZE_KB` (500 KB), `CLONE_TIMEOUT_SECONDS` (60s), and `MAX_CONCURRENT_INDEXING_JOBS` (HTTP `429 Too Many Requests` when saturated).
- **Per-Repository Storage Isolation**: Separate ChromaDB collections (`repo_{id}`), separate SQLite FTS5 databases (`keywords/{id}.db`), separate NetworkX graphs (`graphs/{id}.json`), and cascade deletion (`DELETE /api/v1/repositories/{id}`) wiping all child `chat_messages`, `conversations`, `file_metadata`, `indexing_jobs`, vector indexes, graph files, and workspace folders.

---

### 6. Prompt Injection & Hallucination Defenses
- **Untrusted Input Framing**: System instructions explicitly treat all repository files, READMEs, and code comments as passive untrusted data rather than executable directives (`test_prompt_injection_defense` / `citation_evaluator.py`).
- **Deterministic Gating & Coordinate Validation**: `evaluate_evidence_sufficiency()` prevents generative fabrication when retrieved evidence is `NO_EVIDENCE` or `INSUFFICIENT`, while `CitationValidator` verifies inline citations against actual AST chunk coordinates.
