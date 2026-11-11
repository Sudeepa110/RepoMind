# API Reference

## Base URL & Interactive Docs
- **Base Prefix**: `/api/v1`
- **Swagger / OpenAPI Docs**: `/api/v1/docs` (`/api/v1/openapi.json`)

All responses use JSON unless specified otherwise (`text/event-stream` SSE for `/chat/stream`). When `ENVIRONMENT=production` and `DEBUG=false`, `500` error responses omit internal tracebacks.

---

## 1. System Health & Readiness Probes

### `GET /api/v1/health`
Liveness check reporting backend status, software version, CPU/CUDA hardware mode, and boolean `gemini_configured` flag (API key secret is never returned).

### `GET /api/v1/ready`
Container orchestrator readiness probe verifying SQLite DB connectivity (`SELECT 1`), write permissions on `STORAGE_DIR`, and presence of `chroma`, `graphs`, and `keywords` storage directories (`200 ready` or `503 not_ready`).

---

## 2. Repository Ingestion, Exploration & Lifecycle

Prefix: `/api/v1/repositories`

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/demos` | Curated public GitHub demo repositories. |
| `POST` | `/validate` | Strict SSRF/HTTPS GitHub URL check + availability verification (`api.github.com` + `git ls-remote` fallback). |
| `POST` | `/analyze` | Initiates async shallow clone (`depth=1`), AST parsing, Vector/Graph/Keyword indexing. Returns `429` if `MAX_CONCURRENT_INDEXING_JOBS` exceeded. |
| `GET` | `` | Lists up to 50 recent indexed repositories. |
| `GET` | `/{repository_id}` | Returns language breakdown, manifest files, entry points, commit hash, and README preview. |
| `GET` | `/{repository_id}/status` | Polls indexing stage and percentage progress (`0–100`). |
| `GET` | `/{repository_id}/tree` | Returns nested file directory hierarchy. |
| `GET` | `/{repository_id}/file?path=...` | Reads source file content safely (enforces `is_relative_to` traversal block `400` and blocks secret/excluded files `403`). |
| `POST` | `/{repository_id}/index` | Triggers incremental or forced vector/graph/keyword re-indexing. |
| `GET` | `/{repository_id}/index/status` | Reports indexed ChromaDB chunk count and vector collection status. |
| `POST` | `/{repository_id}/search` | Direct semantic Vector search across code chunks with optional filters (`language`, `file_path`, `symbol_type`). |
| `DELETE` | `/{repository_id}` | Full cascade delete: wipes SQLite child records (`chat_messages`, `conversations`, `file_metadata`, `indexing_jobs`), ChromaDB collection, NetworkX JSON graph, SQLite FTS5 DB, tree JSON, LRU cache, and temporary cloned workspace. |

---

## 3. Adaptive Hybrid Retrieval

Prefix: `/api/v1/repositories/{repository_id}`

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/hybrid-search` | Adaptive Query Router + Vector + Graph + BM25 search combined via Reciprocal Rank Fusion (RRF) with assembled citation context. |
| `POST` | `/analyze-query` | Diagnostic endpoint classifying `QueryIntent`, extracting symbol identifiers, and inspecting routing strategy weights. |

---

## 4. Knowledge Graph Traversal (NetworkX)

Prefix: `/api/v1/repositories/{repository_id}/graph`

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/status` | Total graph nodes, edges, density, and file persistence status. |
| `GET` | `/nodes` | Lists graph nodes filterable by `node_type` (`FUNCTION`, `CLASS`, `FILE`, etc.) or `search` query. |
| `GET` | `/edges` | Lists typed edges (`CALLS`, `IMPORTS`, `CONTAINS`, `INHERITS`, `IMPLEMENTS`). |
| `GET` | `/callers?symbol=...` | Reverse invocation lookup (who calls target symbol). |
| `GET` | `/callees?symbol=...` | Forward invocation lookup (what target symbol invokes). |
| `GET` | `/inheritance?symbol=...` | Base classes and subclasses hierarchy. |
| `GET` | `/dependencies?path=...` | File/module import dependency inspection. |
| `GET` | `/paths?source=...&target=...` | Execution paths connecting two symbols. |
| `GET` | `/impact?symbol=...` | Direct and transitive blast-radius impact nodes. |
| `GET` | `/subgraph?symbol=...` | Localized neighborhood graph for interactive frontend rendering. |

---

## 5. Grounded Conversational Chat & Citations

Prefix: `/api/v1/repositories/{repository_id}`

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/conversations` | Initializes a repository-isolated conversation session. |
| `GET` | `/conversations` | Lists conversation history summaries for the repository. |
| `GET` | `/conversations/{conversation_id}` | Fetches ordered conversation messages, citations, and `insufficient_evidence` flags. |
| `DELETE` | `/conversations/{conversation_id}` | Deletes a specific conversation session and its messages. |
| `POST` | `/chat` | Synchronous grounded generation: hybrid retrieval, repository-wide endpoint matching, evidence sufficiency gating (`SUFFICIENT`, `PARTIAL`, `INSUFFICIENT`, `NO_EVIDENCE`), optional Gemini synthesis, and citation verification. |
| `POST` | `/chat/stream` | Server-Sent Events (SSE) stream emitting `retrieval_started`, `retrieval_completed`, `generation_started`, `token`, `citation`, `warning`, `error`, and `done` events. |

---

## 6. Advanced Repository Intelligence

Prefix: `/api/v1/repositories/{repository_id}/intelligence`

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/impact-analysis` | Multi-file blast radius classifying `DIRECT`, `INDIRECT`, `STRUCTURAL`, and `POTENTIAL` impacted symbols + deterministic risk score. |
| `POST` | `/execution-flow` | Cross-file control-flow tracing with branch points and external boundary flags. |
| `POST` | `/dependencies` | Martin's Instability index ($I = \text{Out} / (\text{In} + \text{Out})$), tightly coupled file pairs, and architectural layers. |
| `POST` | `/bug-investigation` | Static detection of unresolved calls, unguarded API error handlers, null hazards, and resource leaks. |
| `POST` | `/risk-assessment` | Deterministic change-risk scoring breakdown (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`). |
| `POST` | `/test-recommendations` | Discovers existing test files and recommends `UNIT`, `INTEGRATION`, and `REGRESSION` tests with assertions. |
| `POST` | `/documentation` | Generates grounded technical markdown specs for classes, functions, modules, or endpoints. |

---

## 7. Evaluation & Benchmarking

Prefix: `/api/v1/evaluation`

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/summary` | Returns cached evaluation metrics: 4-way retrieval comparison, 72-query balanced abstention, 18-query held-out abstention, grounding/citation metrics, and intelligence accuracy. |
| `GET` | `/system-profile` | Hardware environment profile, RSS memory, indexing stage breakdown, and query latency percentiles (p50/p95/p99). |
| `POST` | `/run` | Executes the complete reproducible evaluation suite across all 6 repositories and persists raw results to `backend/evaluation/results/benchmark_results.json`. |
