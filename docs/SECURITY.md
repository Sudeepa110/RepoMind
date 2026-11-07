# Security & Safety Specifications

## Threat Model & Defenses

RepoMind accepts untrusted third-party input (arbitrary public GitHub repositories) and processes code using an LLM. Strict security controls are implemented at each boundary.

### 1. SSRF & Ingestion Protection
- **Strict Host Checking**: Only URLs matching `https://github.com/{owner}/{repo}` are accepted.
- **Protocol Enforcement**: Only `https` is permitted; `http`, `file://`, `ftp://` are rejected.
- **IP Address & Localhost Blocking**: Hostnames matching `localhost`, `127.0.0.1`, `0.0.0.0`, internal IP addresses (`10.*`, `192.168.*`, `172.16-31.*`) or metadata service endpoints (`169.254.169.254`) are blocked.
- **Port Locking**: Non-standard ports (anything other than 443) are rejected.
- **Credential Disallowance**: URLs containing basic authentication credentials (`user:pass@host`) are immediately rejected.
- **Path Traversal Guards**: Checks prevent `..`, `/etc/`, or backslashes.

### 2. Zero Code Execution Guarantee
- **Cloned Code Isolation**: Repositories are cloned into sandboxed temporary directories (`storage/temp_repos/`).
- **No Build / No Eval**: Cloned code is parsed purely as abstract text and AST syntax trees via Tree-sitter. Code is **never executed**, compiled, or imported into the Python runtime.
- **Automatic Cleanup**: Temporary workspaces are wiped following indexing or upon timeout.

### 3. File & Secret Filtering
- Repositories are filtered during ingestion to omit sensitive credentials:
  - `.env`, `.env.*`, `*.pem`, `*.key`, `*.id_rsa`
  - `.git/` VCS directories
  - `node_modules/`, `venv/`, `dist/`
  - Large binary assets (`*.zip`, `*.exe`, `*.wasm`, `*.mp4`, images)
- Size limits: Configurable thresholds (`MAX_REPO_SIZE_MB`, `MAX_FILE_SIZE_KB`, `MAX_INDEXED_FILES`).

### 4. Prompt Injection Defense
- System prompts explicitly instruct the Gemini LLM that repository contents represent untrusted user data, not instructions.
- System instructions cannot be overridden by comments, READMEs, or documentation inside the target repository.
- Citations must match verified AST chunks stored in the vector database.
