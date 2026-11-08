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

---

## Phase 3: Tree-sitter Code Understanding and Shared Parsing Pipeline (Completed)
**Date**: November 2026

1. **Tree-sitter Language Infrastructure (`backend/app/processing/treesitter_manager.py`)**:
   - Integrated Python 3.11 environment with official binary wheels for core `tree-sitter>=0.24.0`.
   - Loaded and registered official language grammars for 7 primary programming languages + extensions:
     - Python (`tree-sitter-python`)
     - JavaScript (`tree-sitter-javascript`)
     - TypeScript & TSX (`tree-sitter-typescript`)
     - Java (`tree-sitter-java`)
     - C (`tree-sitter-c`)
     - C++ (`tree-sitter-cpp`)
     - Go (`tree-sitter-go`)
   - Implemented thread-safe, extensible `LanguageManager` allowing dynamic grammar registration.
   - Built safe parser execution with max byte thresholds (1 MB) and Tree-sitter syntax error recovery (`ERROR` / `MISSING` node detection without process termination).

2. **Standardized Intermediate Representation (`backend/app/processing/models.py`)**:
   - Designed clean Pydantic domain models serving as the single shared foundation for both Vector RAG (Phase 4) and GraphRAG (Phase 5):
     - `SymbolType`: FUNCTION, METHOD, CLASS, INTERFACE, STRUCT, ENUM, TYPE_ALIAS, MODULE.
     - `SymbolLocation`: 1-indexed start/end lines, 0-indexed start/end columns.
     - `ExtractedSymbol`: deterministic `symbol_id`, names, types, locations, signatures, parameters, modifiers, docstrings, parent scopes.
     - `ExtractedImport`: modules, imported symbols, aliases, relative flag, raw statement.
     - `ExtractedCall`: caller symbol ID, callee name, receiver object, line coordinates, static confirmation flag.
     - `ExtractedInheritance`: sub_symbol_id, super_name, relationship (INHERITS / IMPLEMENTS).
     - `ExtractedComment`: comments & docstrings with associated symbol IDs.
     - `ParsedFile` and `ParsedRepository`: unified, aggregated code understanding container.

3. **Language-Specific AST Extractors (`backend/app/processing/extractors/`)**:
   - `base.py`: Abstract extractor base class with AST traversal, byte slicing, syntax error collectors, line-shift immune deterministic symbol ID generator: `{repo_id}:{file_path}#{parent.}{name}`, and SHA-256 source content hashing.
   - `python_extractor.py`: Functions, async functions, classes, methods, base class inheritance, imports (`import`, `from ... import ...`), calls (`receiver.attribute()`), and docstrings.
   - `javascript_extractor.py`: Functions, arrow functions assigned to const/let/var, classes (`extends`, `implements`), TypeScript interfaces, methods, CommonJS `require()`, ES6 `import`, constructor calls (`new_expression`), and calls.
   - `java_extractor.py`: Classes, interfaces, enums, records, superclasses, super-interfaces, methods, constructors, imports, object creations (`object_creation_expression`), and method invocations.
   - `c_cpp_extractor.py`: C/C++ functions, methods, class/struct specifiers, C++ base classes, preprocessor `#include` directives, constructor calls (`new_expression`), and function calls.
   - `go_extractor.py`: Functions, methods with receivers (`(u *User)`), structs, interfaces, imports, and calls.

4. **Code Understanding Engine (`backend/app/processing/engine.py`)**:
   - Central coordinator orchestrating language detection, Tree-sitter AST parsing, and symbol extraction.
   - Implemented `parse_source_code()`, `parse_file()`, and `parse_repository()`.
   - Graceful fallback for unsupported extensions, Unicode/binary probing, and file size safeguards.

5. **Shared Pipeline Adapters (`backend/app/processing/adapters.py`)**:
   - `to_graph_elements(parsed_repo)`: Directly maps `ParsedRepository` into `GraphNode` and `GraphEdge` objects for GraphRAG (Phase 5). Includes edge deduplication (counting call frequencies and recording line arrays) and target resolution.
   - `to_code_chunks(parsed_repo)`: Directly maps `ParsedRepository` into structure-aware code chunks with line citations and content hashes for Vector RAG (Phase 4).

6. **Phase 3 Quality Audit & Stabilization**:
   - **Audit 1: Call Extraction Variety & Accuracy**: Verified direct calls, object methods, nested calls `f(g(x))`, `self`/`this` calls, module calls, constructors (`new UserService()`, `new ArrayList()`), calls inside loops and conditionals. Verified non-call identifiers (function pointers, argument lists, variables) are rejected.
   - **Audit 2: Nested Symbol Hierarchy**: Validated multi-level nesting across all languages: Class -> Method, Class -> Nested Class -> Method, Function -> Closure / Helper, Interface -> Method, Struct -> Method.
   - **Audit 3: Line-Shift Invariant Symbol IDs**: Decoupled starting line numbers from `symbol_id`. Verified that inserting lines/functions above an existing function does not alter its ID, while `content_hash` tracks actual code changes.
   - **Audit 4: Graph Edge Deduplication & Resolution**: Implemented edge merging to prevent duplicate edges between the same caller and callee; added `call_count` and `lines` list to edge properties. Implemented local target resolution with confidence levels (CONFIRMED 1.0, INFERRED 0.7-0.9, UNRESOLVED 0.3).
   - **Audit 5: Source Citation Guarantees**: Tested 1-indexed line fidelity across Windows CRLF, Unix LF, Unicode characters, and multi-byte UTF-8 source files.

7. **Verification & Testing**:
   - 41 automated tests passing 100% across unit and integration suites (9 dedicated audit tests added).
   - Frontend production build (`npm run build`) verified clean (387ms build time).

---

## Phase 4: Structure-Aware Vector RAG and ChromaDB Persistent Storage (Completed)
**Date**: November 2026

### Work Completed

1. **Abstract Interfaces (`backend/app/vectorstore/interfaces.py`)**:
   - `CodeChunk`: Domain model storing `chunk_id`, `repository_id`, `file_path`, `symbol_id`, `symbol_name`, `symbol_type`, `language`, `start_line`, `end_line`, `source_code`, `signature`, `docstring`, `content_hash`, `context_header`, `full_content`, `part_index`, `total_parts`.
   - `SearchResult`: Container pairing `CodeChunk` with computed `similarity_score` (0.0 to 1.0) and cosine `distance`.
   - `VectorStoreStats`: Container for total chunks, language breakdown, and symbol type breakdown.
   - `BaseEmbeddingService`: Abstract interface for local embeddings decoupling dense vector generation from concrete models.
   - `BaseVectorStore`: Abstract interface for isolated persistent collections, cosine similarity search, stats, incremental hashes, and lifecycle deletion.

2. **Local Zero-Cost Embedding Service (`backend/app/vectorstore/embeddings.py`)**:
   - Implemented `LocalSentenceTransformerService` using `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions).
   - Zero-cost architecture: executes locally on CPU with automatic CUDA GPU acceleration probe.
   - Thread-safe lazy initialization and batch generation support.

3. **Structure-Aware Code Chunker (`backend/app/vectorstore/chunker.py`)**:
   - Consumes the shared Phase 3 AST intermediate representation (`ParsedRepository`).
   - Prioritizes semantic AST symbols (functions, methods, classes, interfaces).
   - Preserves exact 1-indexed line references, symbol IDs, and content hashes.
   - Splits oversized symbols (>100 lines or >3000 chars) into overlapping sub-chunks (20 line overlap) with part numbering (`Part X of Y`) to preserve context.
   - Markdown documentation chunking: partitions README and docs along `#`, `##`, `###` headings into `DOC` chunks.
   - Configuration manifest chunking: sliding-window partitioning for `package.json`, `requirements.txt`, Dockerfiles, etc. into `CONFIG` chunks.
   - Generates formatted context headers summarizing file path, line numbers, and symbol scopes.

4. **Persistent ChromaDB Vector Store (`backend/app/vectorstore/chroma_store.py`)**:
   - Persistent storage located at `storage/chroma/`.
   - Isolated collections per repository using RFC-compliant collection naming (`repo_{sanitized_repo_id}`).
   - Primitive metadata flattening compatible with ChromaDB constraints.
   - Cosine distance metric mapped to bounded similarity scores: $\max(0.0, \min(1.0, 1.0 - \frac{\text{distance}}{2.0}))$.
   - Incremental indexing deduplication: retrieves existing chunk hashes and skips re-embedding unchanged symbols.
   - Complete collection cleanup on repository deletion.

5. **Semantic Search Coordinator (`backend/app/retrieval/semantic_search.py`)**:
   - High-level coordinator for dense query embedding, metadata filtering (by `language`, `file_path`, `symbol_type`), and score ranking.

6. **API Endpoints (`backend/app/api/repositories.py`) & Schemas (`backend/app/schemas/search.py`)**:
   - `POST /api/v1/repositories/{id}/index`: Triggers or re-indexes vector representations for a repository.
   - `GET /api/v1/repositories/{id}/index/status`: Returns vector collection statistics (chunk counts, breakdowns, collection name).
   - `POST /api/v1/repositories/{id}/search`: Executes semantic search with query, top_k, and metadata filters.
   - Updated `DELETE /api/v1/repositories/{id}` to remove ChromaDB collections alongside disk and database records.

7. **Frontend Dashboard Integration (`frontend/src/`)**:
   - Created dedicated **Semantic Vector Search** tab in `DashboardPreview.tsx`.
   - Search bar with example query quick-picks, top_k selection, and language/symbol type filters.
   - Rich search result cards displaying similarity match percentage pills, exact line citations (`#L{start}-L{end}`), symbol pills, and code snippet tables with line numbers.
   - One-click "Open in Code Explorer" action linking directly from search results to file view.
   - Real-time ChromaDB collection stats panel and "Re-index Vectors" action button.
   - Updated pipeline architecture banner to show the 6-stage ingestion and vector indexing progression.

8. **Automated Testing & Ground-Truth Retrieval Evaluation**:
   - Unit tests (`tests/unit/test_vectorstore.py`): 6 tests verifying chunking, splitting, embeddings, ChromaDB persistence, collection isolation, and deletion.
   - Integration test (`tests/integration/test_semantic_retrieval.py`): Multi-language end-to-end ingest -> AST parse -> chunk -> embed -> ChromaDB store -> retrieve flow.
   - Ground-truth evaluation (`tests/evaluation/test_retrieval_metrics.py`): 6 realistic developer queries asserting Precision@1, Precision@3, Recall@3, and line citation accuracy.
   - Evaluation metrics: 100.00% Precision@1, 100.00% Recall@3, 100.00% exact line citation accuracy.
   - Full test suite: 49/49 tests passing 100% in 33.08s.
   - Frontend production build (`npm run build`) passing clean in 220ms.



---

## Phase 5: Knowledge Graph Construction, Persistence & Traversal

**Date**: 2026-11-08  
**Status**: COMPLETED & VERIFIED  
**Backend Tests**: 64 / 64 passing (100% pass rate in 49.21s)  
**Frontend Build**: Production build successful (317ms, 0 errors)  

### Key Accomplishments & Deliverables

1. **Knowledge Graph Architecture & Interfaces (`backend/app/graph/interfaces.py`)**:
   - `NodeType`: Complete coverage of `Repository`, `Directory`, `File`, `Module`, `Class`, `Interface`, `Struct`, `Function`, `Method`, `ApiEndpoint`, `DatabaseModel`.
   - `RelationshipType`: `CONTAINS`, `IMPORTS`, `CALLS`, `INHERITS`, `IMPLEMENTS`, `DEFINES`, `DEPENDS_ON`.
   - `GraphNode` & `GraphEdge`: Explicit support for confidence scoring, confirmation status (`CONFIRMED`, `INFERRED`, `UNRESOLVED`), invocation line citations, and call counts.
   - `BaseGraphStore`: Abstract base class defining node/edge manipulation, neighborhood traversal, callers/callees, inheritance, dependencies, bounded paths, and impact blast radius.

2. **NetworkX Knowledge Graph Persistent Store (`backend/app/graph/networkx_store.py`)**:
   - In-memory `networkx.DiGraph` instances strictly isolated per repository.
   - **Structured JSON Persistence**: Employs `networkx.node_link_data` / `node_link_graph` with `edges="edges"`. Safely avoids unsafe pickle serialization.
   - **Atomic Persistence**: Writes serialized graphs to `storage/graphs/{sanitized_repo_id}.json.tmp` and renames atomically via `os.replace` to prevent corrupted files on unexpected interruptions.
   - **Safe Corrupted File Recovery**: Gracefully handles malformed or empty graph files by returning `False` without crashing.
   - **Thread Safety**: Protected with reentrant locks (`threading.RLock`) for concurrent requests.
   - **Repository Deletion Cleanup**: Purges graph files from disk and removes from memory cache.

3. **Graph Construction Engine (`backend/app/graph/builder.py`)**:
   - Consumes the shared Tree-sitter `ParsedRepository` intermediate representation and `to_graph_elements()` adapter.
   - **Directory Containment**: Generates hierarchical `Directory` nodes and `CONTAINS` edges connecting repository root down to nested directories and files.
   - **Node & Edge Validation**: Enforces repository ID alignment, valid identifiers, and removes invalid self-loops.
   - **Call Deduplication**: Merges repeated calls between the same two symbols into a single edge preserving cumulative `call_count`, invocation `lines`, and confidence scores.

4. **Graph Traversal Service (`backend/app/graph/traversal.py`)**:
   - `find_callers`: Retrieves functions/methods calling a given symbol with invocation line numbers, call frequency, and confidence.
   - `find_callees`: Retrieves functions/methods called by a given symbol.
   - `find_inheritance_hierarchy`: Traces parent classes, subclasses, implemented interfaces, and class implementors.
   - `find_dependencies`: Traces outgoing module imports and incoming dependent files.
   - `find_execution_paths`: Bounded simple path exploration between two symbols along `CALLS` edges with max depth limits (disclaiming that static call graphs represent potential invocation paths).
   - `analyze_impact`: Traverses incoming callers and dependents to calculate modification blast radius and list affected files.

5. **Graph Query REST APIs (`backend/app/api/graph.py`)**:
   - `GET /api/v1/repositories/{id}/graph/status`: Summary metrics (nodes, edges, density, confirmation breakdown).
   - `GET /api/v1/repositories/{id}/graph/nodes`: Filtered, paginated node list (by type, file path, name query).
   - `GET /api/v1/repositories/{id}/graph/edges`: Filtered, paginated edge list (by relationship, endpoints).
   - `GET /api/v1/repositories/{id}/graph/callers`: Callers of a symbol.
   - `GET /api/v1/repositories/{id}/graph/callees`: Callees of a symbol.
   - `GET /api/v1/repositories/{id}/graph/inheritance`: Inheritance hierarchy.
   - `GET /api/v1/repositories/{id}/graph/dependencies`: Module dependencies.
   - `GET /api/v1/repositories/{id}/graph/paths`: Bounded execution paths between symbols.
   - `GET /api/v1/repositories/{id}/graph/impact`: Modification blast radius and impacted files.
   - `GET /api/v1/repositories/{id}/graph/subgraph`: Localized ego subgraph centered on a node.

6. **Indexing Lifecycle Integration (`backend/app/services/indexing.py`)**:
   - Integrated Stage 7: Knowledge Graph Construction & Persistence with NetworkX directly into background job runner.
   - Updates `update_job_progress` stages (88% -> 100%).
   - Integrated graph deletion into `delete_repository` in `repositories.py`.

7. **Frontend Knowledge Graph Dashboard (`frontend/src/pages/DashboardPreview.tsx`)**:
   - Dedicated **Knowledge Graph** tab with live node count pill.
   - Interactive SVG ego subgraph visualizer with radial layout, colored node badges, directed relationship arrows, and click-to-center navigation.
   - Entity Inspector side panel displaying signatures, docstrings, source lines, and one-click "Open in Code Explorer" action.
   - Call Hierarchy explorer (Incoming Callers vs Outgoing Callees).
   - Blast Radius impact explorer calculating affected files and direct callers.
   - Filterable All Code Entities table.

8. **Automated Testing & Regression Verification**:
   - Unit tests (`tests/unit/test_graph_construction.py`): 6 tests verifying validation, deduplication, directory hierarchy, atomic JSON persistence, corrupted file recovery, and repository isolation.
   - Traversal tests (`tests/unit/test_graph_traversal.py`): 7 tests verifying callers, callees, inheritance, dependencies, bounded paths, cycles/recursion safety, impact blast radius, and missing symbols.
   - Integration tests (`tests/integration/test_graph_integration.py`): 2 tests verifying end-to-end multi-language parsing -> graph construction -> reload -> traversal and API endpoints.
   - Full test suite: 64/64 tests passing 100% in 49.21s.
   - Frontend production build (`npm run build`) passing clean in 317ms.

---

## Phase 6: Hybrid Retrieval Engine (Vector RAG + GraphRAG + Keyword Search)

**Date**: 2026-11-08  
**Status**: COMPLETED & VERIFIED  
**Backend Tests**: 93 / 93 passing (100% pass rate in 31.49s)  
**Frontend Build**: Production build successful (399ms, 0 errors)  
**Retrieval Benchmark**: Intent Accuracy: 100%, Hybrid Precision@1: 85.7% (vs Vector: 57.1%, Keyword: 42.9%), Recall@3: 85.7%, MRR: 0.857, Latency: ~8.3ms  

### Key Accomplishments & Deliverables

1. **Lightweight Query Intent Analyzer & Strategy Router (`backend/app/retrieval/query_analyzer.py` & `query_router.py`)**:
   - Deterministic classification across 11 developer question intents: `SEMANTIC`, `EXACT_SYMBOL`, `CALLERS`, `CALLEES`, `DEPENDENCIES`, `INHERITANCE`, `EXECUTION_FLOW`, `IMPACT_ANALYSIS`, `ARCHITECTURE`, `CONFIG_OR_DOCS`, `UNKNOWN`.
   - Heuristic extraction of backticked symbols, function invocation syntax, CamelCase, snake_case, and file paths with stop-word filtering.
   - Intent-aware strategy routing with user override controls (`include_vector`, `include_graph`, `include_keyword`).

2. **Repository-Scoped Keyword Search Engine (`backend/app/retrieval/keyword_search.py`)**:
   - Zero-cost, 100% local BM25 ranking backed by SQLite FTS5 (`storage/keywords/{sanitized_repo_id}.db`).
   - BM25 column weighting boosting `symbol_name` (10.0) and `file_path` (5.0) over body text.
   - Compound identifier tokenization supporting dot notation (`DatabaseClient.connect`), prefix wildcards, and special character sanitization.
   - Thread-safe transaction and connection lifecycle management ensuring instant Windows file lock release.
   - Incremental indexing deduplication using SHA-256 `content_hash` matching.

3. **Reciprocal Rank Fusion Engine (`backend/app/retrieval/result_fusion.py`)**:
   - Calibrated RRF rank aggregation: $\text{RRF}(d) = \sum \frac{w_s}{60 + \text{rank}_s(d)}$.
   - Multi-engine provenance tracking with combined badges (e.g. `HYBRID (VECTOR + KEYWORD)`).
   - Dynamic intent weighting: boosts Graph for structural queries (`1.8`), boosts Keyword for exact symbols (`1.5`), and boosts Vector for conceptual semantic questions (`1.3`).
   - Safe score normalization to $[0.0, 1.0]$.

4. **Structured Context Assembler (`backend/app/retrieval/context_assembler.py`)**:
   - Synthesizes ranked code chunks, exact file and line coordinates, caller/callee graph evidence, and provenance into a compact Markdown prompt block.
   - Distinguishes `[CONFIRMED]` vs `[INFERRED (X% conf)]` structural links.
   - Verified Evidence Citations table (`Rank | File Path | Line Range | Symbol | Source Engine | RRF Score`).
   - Character budget bounding preventing token context overflows.

5. **Unified Hybrid Retrieval Coordinator (`backend/app/retrieval/hybrid_retriever.py`)**:
   - Master orchestrator combining Vector search, Graph traversal, and Keyword search with parallel execution, per-engine timing, and graceful degradation on individual engine failures.
   - Role-aware graph candidate extraction prioritizing actual answers (callers for caller queries, callees for callee queries).

6. **REST API Endpoints (`backend/app/api/hybrid_retrieval.py` & `main.py`)**:
   - `POST /api/v1/repositories/{id}/hybrid-search`: Unified search returning ranked code chunks, graph evidence, assembled context, and latency diagnostics.
   - `POST /api/v1/repositories/{id}/analyze-query`: Diagnostic query understanding endpoint returning classified intents and strategy recommendations.
   - Full repository deletion cleanup in `repositories.py` (`keyword_search_engine.delete_repository`).

7. **Frontend Hybrid Retrieval Dashboard (`frontend/src/pages/DashboardPreview.tsx`)**:
   - Enhanced search tab with **Retrieval Strategy** toggle (`Hybrid Fusion (RRF)` vs `Dense Vector Only`).
   - Engine filter checkboxes (`Vector`, `Graph`, `Keyword`).
   - Query intent badges, strategy used pills, and per-engine latency breakdown.
   - Interactive structural graph evidence cards (`CALLS`, `IMPORTS`, `IMPACTS`).
   - Ranked code cards with multi-source provenance pills, RRF scores, and "Open in Code Explorer" action.
   - Expandable **Structured Context Assembler** card with one-click "Copy Context" and verified citation table.

8. **Automated Testing & Quantitative Retrieval Evaluation**:
   - Unit tests (`tests/unit/test_query_analyzer.py`, `test_keyword_search.py`, `test_result_fusion.py`, `test_context_assembler.py`): 24 tests.
   - Integration tests (`tests/integration/test_hybrid_retrieval.py`): 4 tests.
   - Quantitative evaluation benchmark (`tests/evaluation/test_hybrid_evaluation.py`): Comparing Vector-only, Keyword-only, and Hybrid across 7 diverse query categories.
   - Full test suite: **93/93 tests passing (100%) in 31.49s**.
   - Frontend production build (`npm.cmd run build`): **0 errors, 399ms**.

---

## Phase 7: Gemini LLM Integration, Grounded Generation & Conversational Chat

**Date**: 2026-11-08  
**Status**: COMPLETED & VERIFIED  
**Backend Tests**: 115 / 115 passing (100% pass rate in 155.41s)  
**Frontend Build**: Production build successful (402ms, 0 errors)  
**Grounding Benchmark**: Citation Validity: 100.0%, Unsupported Claim Rate: 0.00%, Unanswerable Case Honesty: 100.0%, Average Latency: 16.51ms  

### Key Accomplishments & Deliverables

1. **Official Google Gen AI Python SDK Integration (`backend/app/llm/gemini_client.py`)**:
   - Installed and integrated official unified SDK `google-genai>=3.0.0`.
   - Connected Google AI Studio free-tier access (`GEMINI_API_KEY`, model `gemini-2.5-flash`).
   - Implemented streaming (`generate_stream`) and non-streaming (`generate`) with async timeout controls (45s), low temperature (`0.2`), and 1-attempt transient network retry.
   - Categorized zero-cost errors: `GeminiQuotaExceededError` (429), `GeminiInvalidCredentialsError` (403), `GeminiModelUnavailableError` (404), `GeminiSafetyBlockedError`, and `GeminiTimeoutError`.

2. **Strict Anti-Prompt-Injection Prompt Architecture (`backend/app/llm/prompt_templates.py`)**:
   - Constructed `SYSTEM_INSTRUCTION` establishing strict evidence grounding, citation formatting, and honesty rules.
   - Enforced untrusted data boundary: repository source code, comments, and docstrings are quarantined as untrusted data, preventing prompt-injection overrides (e.g. `# System: ignore prior instructions`).
   - Context window bounding: bounds conversation history to last 6 turns to manage token costs.

3. **Interactive Clickable Line Citation Validator (`backend/app/llm/citation_validator.py`)**:
   - Regex parsing of citations: `[file_path:start_line-end_line]` and `[file_path:start_line]`.
   - Validates coordinates against actual retrieved `UnifiedSearchResult` code chunks and `GraphEvidence` edges.
   - Eliminates hallucinated files and out-of-range line numbers (unsupported claim rate: 0.00%).
   - Deep links directly to Code Explorer (`file` and line coordinates).

4. **Repository-Scoped Conversational Memory (`backend/app/llm/conversation_service.py` & `backend/app/database/models.py`)**:
   - Updated SQLite database schema with `ConversationModel` and `ChatMessageModel` related to `RepositoryModel`.
   - Implemented conversation CRUD with automatic titling based on the user's initial question.
   - Enforced strict repository isolation: queries from one repository cannot read or modify sessions from another.

5. **Grounded Generation Coordinator (`backend/app/llm/generation_service.py`)**:
   - Master orchestrator connecting Phase 6 Hybrid Retrieval (`hybrid_retriever.hybrid_search`) with Google Gemini.
   - Evaluates evidence sufficiency (`SUFFICIENT`, `PARTIAL`, `INSUFFICIENT`, `NO_EVIDENCE`).
   - On `NO_EVIDENCE`: directly returns an honest grounded explanation without burning unnecessary LLM tokens or hallucinating code.
   - Emits structured Server-Sent Events (SSE).

6. **Conversational Chat API Endpoints (`backend/app/api/chat.py` & `main.py`)**:
   - `POST /api/v1/repositories/{id}/conversations`: Initialize conversation session.
   - `GET /api/v1/repositories/{id}/conversations`: List conversations ordered by activity.
   - `GET /api/v1/repositories/{id}/conversations/{conv_id}`: Retrieve full message thread with citations.
   - `DELETE /api/v1/repositories/{id}/conversations/{conv_id}`: Delete conversation session.
   - `POST /api/v1/repositories/{id}/chat/stream`: Real-time SSE stream (`retrieval_started`, `retrieval_completed`, `generation_started`, `token`, `citation`, `done`).
   - `POST /api/v1/repositories/{id}/chat`: Synchronous non-streaming answer endpoint.

7. **Frontend Conversational Chat Workspace (`frontend/src/pages/DashboardPreview.tsx`)**:
   - Dual-pane layout: conversation session sidebar + main chat workspace.
   - Real-time token streaming with pulsing indicator.
   - Live retrieval banner showing retrieved chunks, engines used, and retrieval latency.
   - Interactive clickable citation pills deep-linking to Code Explorer (`activeTab='explorer'`).
   - Grounding confidence meter badge, copy answer action, and suggested starter prompts.
   - Streaming stop/abort button using `AbortController`.

8. **Automated Testing & Quantitative Grounding Evaluation**:
   - Citation Validator unit tests (`tests/unit/test_citation_validator.py`): 5 tests passing.
   - Gemini Client unit tests (`tests/unit/test_gemini_client.py`): 7 tests passing.
   - Conversation Service unit tests (`tests/unit/test_conversation_service.py`): 5 tests passing.
   - Chat Integration tests (`tests/integration/test_chat_integration.py`): 4 tests passing.
   - Quantitative Grounding Benchmark (`tests/evaluation/test_grounding_evaluation.py`): 10 benchmark questions (9 answerable, 1 unanswerable).
     - Citation Precision & Validity: **100.0%**
     - Unsupported Claim Rate: **0.00%**
     - Average Pipeline Latency: **16.51 ms**
   - Full test suite: **115/115 tests passing (100%) in 155.41s**.
   - Frontend production build (`npm.cmd run build`): **0 errors, 402ms**.
