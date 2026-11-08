# System Architecture: Hybrid Vector RAG + GraphRAG

## Architecture Overview

RepoMind combines **Vector RAG** (semantic meaning of code, comments, documentation) and **GraphRAG** (structural relationships, function calls, inheritance, dependencies) through a shared Tree-sitter code understanding foundation.

```mermaid
flowchart TD
    subgraph Ingestion["Ingestion & Sanitization"]
        URL["GitHub Repository URL"] --> Validate["URL Validation & SSRF Guard"]
        Validate --> Clone["Isolated Shallow Clone (depth=1)"]
        Clone --> Filter["File Filter (Strips binaries, secrets, node_modules)"]
    end

    subgraph Parsing["Shared Code Understanding Layer"]
        Filter --> TreeSitter["Tree-sitter Multi-Language AST Parser"]
        TreeSitter --> AST["Syntactic AST Nodes (Functions, Classes, Imports, Calls)"]
    end

    subgraph PipelineA["Pipeline A: Vector RAG"]
        AST --> Chunker["Structure-Aware Chunker"]
        Chunker --> Embedder["Sentence Transformers (Local MiniLM-L6-v2)"]
        Embedder --> ChromaDB[("ChromaDB Vector Store")]
    end

    subgraph PipelineB["Pipeline B: GraphRAG"]
        AST --> GraphBuilder["Node & Relationship Extractor"]
        GraphBuilder --> NetworkX[("Knowledge Graph (NetworkX Engine)")]
    end

    subgraph Hybrid["Unified Retrieval & Synthesis Engine"]
        UserQuery["User Natural Language Query"] --> QueryRouter{"Query Intent Router"}
        QueryRouter -->|Semantic / Overview| ChromaDB
        QueryRouter -->|Call Hierarchy / Dependencies| NetworkX
        QueryRouter -->|Execution Flow / Impact Analysis| Both["Hybrid Fusion (Vector + Graph)"]
        
        ChromaDB --> Reranker["Context Fusion, Deduplication & Reranker"]
        NetworkX --> Reranker
        Both --> Reranker
        
        Reranker --> ContextBuilder["RAG Context Builder"]
        ContextBuilder --> Gemini["Google Gemini API (Free Tier)"]
        Gemini --> Response["Grounded Answer with Clickable Source Citations"]
    end
```

---

## 1. Shared Code Understanding Layer

To prevent duplicated parsing logic and inconsistencies between vector chunks and graph nodes, Tree-sitter serves as the single source of truth:

- **Functions & Methods**: Name, parameters, return type, start/end line coordinates, parent class/module.
- **Classes & Interfaces**: Name, base classes, implemented interfaces, declared methods, line coordinates.
- **Imports & Dependencies**: Imported modules, symbols, relative/absolute targets.
- **Call Sites**: Statically identifiable call invocations (`obj.method()`, `func()`, `new Class()`).
- **Parent-Child Scopes**: Containing module, namespace, or class hierarchy.

### Symbol Identity & Content Fingerprinting Strategy

Symbol identifiers in RepoMind follow a deterministic, line-independent structure:
`{repository_id}:{file_path}#{parent_scope.}{symbol_name}` (with `::{disambiguation_idx}` for overloads).

- **Line-Shift Immunity**: Line numbers are intentionally treated as source-location metadata (`SymbolLocation.start_line`), not part of the symbol's unique ID. This ensures that inserting unrelated code or blank lines above a symbol does not invalidate graph edges or vector chunk caches.
- **Content Hash (`content_hash`)**: A 16-character SHA-256 fingerprint of normalized source code. This enables fast incremental re-indexing: an unchanged symbol preserves both its ID and its content hash.

### Call Extraction & Resolution Classification

Static call extraction distinguishes between confirmed syntax, inferred relationships, and unresolved dynamic dispatches:

- **CONFIRMED (Confidence 1.0)**: Direct calls to locally defined functions/classes in the same file, method calls on `self`/`this` matching local class methods, or calls matching explicitly imported module symbols.
- **INFERRED (Confidence 0.6 - 0.9)**: Static calls on typed/imported receivers (e.g., `math.sqrt`, `logger.info`, `user.calculate()`) or recognized standard library built-ins.
- **UNRESOLVED (Confidence 0.3)**: Dynamic dispatch, indirect invocations, reflection (`getattr()`), or higher-order callbacks where the runtime target cannot be statically guaranteed.
- **Constructor Calls**: Native detection of instantiation across languages (`new_expression` in JS/TS/C++, `object_creation_expression` in Java, class calls in Python).

### Known Static Analysis Limitations

1. **Dynamic Method Dispatch**: Python `getattr(obj, "method")()` and JavaScript `obj[methodName]()` cannot be resolved to a specific AST node statically.
2. **Untyped Duck Typing**: Calls on untyped Python parameters `param.execute()` or JavaScript arguments are mapped as `INFERRED` / `UNRESOLVED` rather than falsely confirmed.
3. **Macro Expansions in C/C++**: Complex preprocessor macro expansions that synthesize function definitions at compile-time are partially parsed as raw AST blocks.

---

## 2. Pipeline A: Vector RAG & Persistent Storage (Phase 4 Completed)

Responsible for retrieving semantically relevant code snippets, comments, docstrings, and architectural summaries:
- **Chunker (`StructureAwareChunker`)**:
  - Direct consumption of Phase 3 AST intermediate representation (`ParsedRepository`).
  - Prioritizes semantic AST symbols (functions, methods, classes, interfaces).
  - Preserves exact 1-indexed line references, symbol IDs, and SHA-256 `content_hash` fingerprints.
  - Splits oversized symbols (>100 lines or >3000 chars) into overlapping sub-chunks (20 line overlap) with part indicators (`Part X of Y`) without dropping surrounding context.
  - Semantic fallback chunking for Markdown documentation (`DOC` symbols split on `#`, `##`, `###` headings).
  - Sliding-window fallback chunking for configuration manifests (`package.json`, `requirements.txt`, Dockerfiles).
- **Embedding Model (`LocalSentenceTransformerService`)**:
  - `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional dense vectors).
  - Zero-cost, 100% local CPU execution with automatic CUDA GPU acceleration probe.
  - Batching support (default batch size 32) and normalized cosine embeddings.
- **Vector Database (`ChromaVectorStore`)**:
  - Persistent ChromaDB storage located at `storage/chroma/`.
  - Strict repository collection isolation via sanitized collection identifiers (`repo_{sanitized_repo_id}`).
  - Primitive metadata flattening (`repository_id`, `file_path`, `symbol_id`, `symbol_name`, `symbol_type`, `language`, `start_line`, `end_line`, `content_hash`, `part_index`).
  - Cosine distance metric with bounded similarity scores (`1.0 - distance / 2.0`).
  - Incremental indexing deduplication: skips embedding chunks whose `content_hash` has not changed.
  - Complete repository lifecycle cleanup (`delete_repository`).
- **Retrieval Service (`SemanticSearchService`)**:
  - High-level query embedding and semantic search with metadata filtering (language, file path, symbol type).
  - Validated ground-truth benchmarks: 100% Precision@1, 100% Recall@3, and 100% exact line citation accuracy.

---

## 3. Pipeline B: Knowledge Graph & GraphRAG

Responsible for modeling and traversing structural relationships, call hierarchies, inheritance, and dependencies:
- **Graph Engine (`NetworkXGraphStore`)**:
  - Implements `BaseGraphStore` abstraction isolating graph storage, ensuring seamless future migration to Neo4j without modifying business logic.
  - In-memory `networkx.DiGraph` instances strictly isolated per repository.
  - **Structured JSON Persistence**: Uses safe node-link format (`networkx.node_link_data` / `node_link_graph` with `edges="edges"`), completely avoiding unsafe pickle serialization.
  - **Atomic Persistence**: Writes serialized graphs to `storage/graphs/{sanitized_repo_id}.json.tmp` and renames atomically via `os.replace` to prevent corrupted files on unexpected interruptions.
  - **Safe Corrupted File Recovery**: Automatically logs warnings and returns graceful defaults on corrupted files rather than crashing the API process.
  - **Thread Safety**: Protected by reentrant locks (`threading.RLock`) for concurrent requests.
- **Graph Construction (`GraphBuilder`)**:
  - Consumes the shared Tree-sitter `ParsedRepository` intermediate representation and `to_graph_elements()` adapter.
  - **Directory Containment**: Generates hierarchical `Directory` nodes and `CONTAINS` edges from repository root to nested directories and files.
  - **Node & Edge Validation**: Enforces repository ID alignment, valid identifiers, and removes invalid self-loops.
  - **Call Deduplication**: Merges repeated calls between the same two symbols into a single edge preserving cumulative `call_count`, invocation `lines`, and confidence scores.
  - **Resolution Classification**: Distinguishes `CONFIRMED` local links from `INFERRED` repository matches and `UNRESOLVED` external symbols.
- **Graph Traversal Service (`GraphTraversalService`)**:
  - `find_callers`: Retrieves functions/methods calling a given symbol with invocation line numbers, call frequency, and confidence.
  - `find_callees`: Retrieves functions/methods called by a given symbol.
  - `find_inheritance_hierarchy`: Traces parent classes, subclasses, implemented interfaces, and class implementors.
  - `find_dependencies`: Traces outgoing module imports and incoming dependent files.
  - `find_execution_paths`: Bounded simple path exploration between two symbols along `CALLS` edges with max depth limits (disclaiming that static call graphs represent potential invocation paths).
  - `analyze_impact`: Traverses incoming callers and dependents to calculate modification blast radius and list affected files.
- **Graph Query APIs**:
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
- **Frontend Knowledge Graph Dashboard**:
  - Dedicated tab with interactive SVG canvas, radial layout, color-coded node badges, and directed relationship labels.
  - Entity Inspector side panel with source lines and one-click **"Open in Code Explorer"** deep link.
  - Interactive Call Hierarchy explorer and Blast Radius impact view.

---

## 4. Unified Hybrid Retrieval & Context Fusion

The Query Router inspects incoming questions and directs them dynamically:

| Question Type | Example | Retrieval Strategy |
|---|---|---|
| Semantic / Conceptual | "Explain authentication in this project" | Vector RAG |
| Symbol / Call Graph | "Which functions call loginUser()?" | GraphRAG |
| Cross-cutting / Flow | "Explain the complete login execution flow" | Hybrid (Vector + Graph) |
| Change Impact | "What could be affected if I modify AuthService?" | Hybrid (Vector + Graph) |

The Context Builder synthesizes retrieved vector chunks alongside graph relationship summaries into a unified prompt context for Google Gemini, ensuring every fact is backed by clickable file and line citations.
