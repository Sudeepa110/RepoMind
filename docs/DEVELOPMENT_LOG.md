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

