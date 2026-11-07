# Development Log

## Phase 1: Project Foundation & Baseline Scaffolding
- **Status**: Completed Successfully
- **Date**: 2026-11-07
- Built FastAPI backend with `/api/v1/health` and `/api/v1/repositories/validate`.
- Built React 19 + TypeScript + Tailwind CSS v4 dashboard.
- Configured Git, `.gitignore`, Docker Compose, and environment settings.
- 100% test pass rate on unit and integration suites.

---

## Architectural Update: Hybrid Vector RAG + GraphRAG
- **Status**: Completed Foundation Integration
- **Date**: 2026-11-07
- **Architectural Decision**:
  - Adopted dual-pipeline retrieval architecture combining **Vector RAG** (ChromaDB + Sentence Transformers) and **GraphRAG** (NetworkX Knowledge Graph).
  - Designed single shared parsing foundation powered by Tree-sitter to feed both vector chunking and graph construction.
  - Defined `BaseGraphStore` modular interface in `backend/app/graph/interfaces.py` to decouple graph operations from underlying storage (allowing zero-friction migration to Neo4j if scale demands).
  - Updated storage configuration to allocate `storage/graphs/` alongside `storage/chroma/` and `storage/repomind.db`.
  - Defined unified Hybrid Retrieval strategy with query intent classification.

---

## Updated Master 10-Phase Roadmap

- **Phase 1**: Project Foundation & Baseline Scaffolding *(Completed)*
- **Phase 2**: GitHub Repository Ingestion & File Filtering *(Completed & Verified)*
- **Phase 3**: Tree-sitter Code Understanding & Shared Parsing Pipeline
- **Phase 4**: Vector RAG & ChromaDB Persistent Storage
- **Phase 5**: Knowledge Graph Construction using NetworkX
- **Phase 6**: GraphRAG & Graph Traversal (Call graphs, Dependencies, Scopes)
- **Phase 7**: Unified Hybrid Retrieval, Query Routing & Context Fusion
- **Phase 8**: Gemini Integration, Grounded Generation & Clickable Citations
- **Phase 9**: Advanced Repository Intelligence & Change Impact Analysis
- **Phase 10**: Multi-User Security, Performance Optimization & Public Deployment

---

## Phase 2: GitHub Repository Ingestion & File Filtering
- **Status**: Completed & Verified
- **Date**: 2026-11-07

### Work Completed

1. **Repository Cloner (`backend/app/ingestion/cloner.py`)**:
   - Implemented shallow cloning (`git clone --depth 1 --single-branch --no-tags`) into isolated temporary workspaces (`storage/temp_repos/{uuid}/`).
   - Configured non-interactive execution (`GIT_TERMINAL_PROMPT=0`, `GCM_INTERACTIVE=never`, `stdin=subprocess.DEVNULL`) to prevent credential prompts or UI hangs on private/nonexistent repos.
   - Enforced disk size limits (`MAX_REPO_SIZE_MB`) and timeouts (`CLONE_TIMEOUT_SECONDS`).
   - Implemented Windows-safe workspace cleanup handling read-only git attributes.

2. **File Filtering Engine (`backend/app/ingestion/file_filter.py`)**:
   - Filtered build, dependency, and VCS directories (`.git`, `node_modules`, `venv`, `dist`, `build`, etc.).
   - Filtered binary and compiled extensions (`.exe`, `.dll`, `.so`, `.zip`, `.pyc`, `.png`, `.jpg`, `.sqlite`, `.wasm`, etc.).
   - Implemented secret and credential detection (`.env*`, `*.pem`, `*.key`, `id_rsa`, `credentials.json`, `service_account.json`).
   - Null-byte binary content probing on file reads.
   - Enforced `MAX_FILE_SIZE_KB` (500 KB) and `MAX_INDEXED_FILES` (500 files).

3. **Repository Analyzer (`backend/app/ingestion/analyzer.py`)**:
   - Language detection mapping 30+ extensions to languages with line counts and percentages.
   - Dependency manifest detection (`package.json`, `pyproject.toml`, `requirements.txt`, `Cargo.toml`, `Dockerfile`, etc.).
   - Entry point candidate detection (`main.py`, `app.py`, `index.ts`, `server.js`, etc.).
   - Truncated README extraction (up to 100 KB).
   - Hierarchical directory tree generator (`TreeNode`) for the Code Explorer.

4. **Background Indexing Service (`backend/app/services/indexing.py`)**:
   - Async background worker tracking stages: `QUEUED` -> `CLONING` -> `FILTERING` -> `ANALYZING` -> `COMPLETED`.
   - SQLite persistence for repository metadata, job tracking, and file cataloging.

5. **API Endpoints (`backend/app/api/repositories.py`)**:
   - `POST /api/v1/repositories/analyze`
   - `GET /api/v1/repositories/{id}/status`
   - `GET /api/v1/repositories/{id}`
   - `GET /api/v1/repositories/{id}/tree`
   - `GET /api/v1/repositories/{id}/file?path=...` (with path-traversal guards)
   - `GET /api/v1/repositories`
   - `DELETE /api/v1/repositories/{id}`

6. **Frontend Integration**:
   - `DashboardPreview.tsx` updated with real-time progress polling, stage indicators, language distribution bars, manifest/entry point lists, interactive directory tree, and file viewer with line numbering.

7. **Verification & Testing**:
   - 19 automated tests passing 100% across unit and integration suites.
   - Verified real shallow cloning and analysis against multiple public repositories (`octocat/Hello-World`, `octocat/Spoon-Knife`, `expressjs/cookie-parser`).
   - Path-traversal attacks and invalid URLs verified to be rejected cleanly.
