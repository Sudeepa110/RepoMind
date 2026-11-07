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
- **Call Sites**: Statically identifiable call invocations (`obj.method()`, `func()`).
- **Parent-Child Scopes**: Containing module, namespace, or class hierarchy.

---

## 2. Pipeline A: Vector RAG

Responsible for retrieving semantically relevant code snippets, comments, docstrings, and architectural summaries:
- **Chunker**: Logical structure-aware chunking preserving syntax integrity.
- **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional dense vectors generated locally).
- **Vector Database**: ChromaDB collections partitioned per repository.
- **Retrieval**: Dense cosine similarity + sparse BM25 keyword matching with Reciprocal Rank Fusion.

---

## 3. Pipeline B: GraphRAG

Responsible for modeling and traversing structural relationships and dependencies:
- **Graph Engine**: NetworkX with JSON/GraphML persistence in `storage/graphs/{repo_id}.json`.
- **Abstract Interface**: `BaseGraphStore` abstraction isolating graph storage, ensuring seamless future migration to Neo4j without modifying business logic.
- **Graph Nodes**:
  - `Repository`, `Directory`, `File`, `Module`, `Class`, `Interface`, `Function`, `Method`, `ApiEndpoint`, `DatabaseModel`.
- **Graph Relationships**:
  - `CONTAINS` (directory -> file, class -> method)
  - `IMPORTS` (file -> module)
  - `CALLS` (function -> function/method)
  - `INHERITS` (class -> base class)
  - `IMPLEMENTS` (class -> interface)
  - `DEFINES` (file -> symbol)
  - `DEPENDS_ON` (component -> component)

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
