# Data Flow Specification: Hybrid Vector RAG + GraphRAG

## 1. Dual Ingestion & Indexing Flow

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Frontend as React Frontend
    participant API as FastAPI Backend
    participant Worker as Indexing Service
    participant TreeSitter as Tree-sitter Parser
    participant Chroma as ChromaDB (Vector RAG)
    participant Graph as NetworkX (GraphRAG)
    participant SQLite as SQLite Metadata DB

    User->>Frontend: Enter GitHub Repo URL & Submit
    Frontend->>API: POST /api/v1/repositories/analyze
    API->>SQLite: Insert repo record (status: QUEUED)
    API-->>Frontend: Return Job ID
    
    API->>Worker: Launch background ingestion
    Worker->>Worker: Shallow clone & sanitize files
    Worker->>TreeSitter: Parse source files into AST nodes
    
    par Vector Pipeline
        TreeSitter->>Chroma: Structure-aware chunks + MiniLM embeddings
    and Graph Pipeline
        TreeSitter->>Graph: Construct nodes & relationships (CALLS, IMPORTS, INHERITS)
    end
    
    Worker->>Graph: Persist knowledge graph to storage/graphs/
    Worker->>SQLite: Update repository status: READY
```

---

## 2. Hybrid Query & Grounded Answer Flow

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Frontend as React Frontend
    participant API as FastAPI Backend
    participant Router as Query Intent Router
    participant Chroma as ChromaDB Vector Store
    participant Graph as NetworkX Graph Store
    participant Builder as Context Builder
    participant Gemini as Google Gemini API

    User->>Frontend: Ask: "What happens when loginUser() is called?"
    Frontend->>API: POST /api/v1/chat/{repo_id}
    API->>Router: Classify query intent
    
    par Parallel Retrieval
        Router->>Chroma: Dense vector search for semantic concepts
        Chroma-->>Router: Top-K code chunks
    and Graph Traversal
        Router->>Graph: Traverse call chain & dependencies for loginUser()
        Graph-->>Router: Subgraph of callers, callees & imports
    end
    
    Router->>Builder: Merge vector snippets + graph relationship tree
    Builder->>Gemini: Stream prompt with strict citation constraints
    Gemini-->>API: Grounded response with verified line references
    API-->>Frontend: SSE Stream (Text + Clickable Citations)
    Frontend-->>User: Render syntax-highlighted answer with line links

---

## 3. Semantic Vector Search Flow (Phase 4 Completed)

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Frontend as React Dashboard (Search Tab)
    participant API as FastAPI Backend (/repositories/{id}/search)
    participant SearchService as SemanticSearchService
    participant Embedder as Local MiniLM-L6-v2 Embedder
    participant Chroma as ChromaDB Isolated Collection
    participant Explorer as Code Explorer (UI)

    User->>Frontend: Enter query: "JWT token verification" + optional filters
    Frontend->>API: POST /api/v1/repositories/{id}/search (query, top_k, filters)
    API->>SearchService: search(repo_id, query, top_k, language, file_path, symbol_type)
    SearchService->>Embedder: embed_text(query) -> 384-dim dense float vector
    SearchService->>Chroma: collection.query(query_embedding, where=filters, n_results=top_k)
    Chroma-->>SearchService: documents, metadatas, distances
    SearchService->>SearchService: Compute cosine similarity (1.0 - distance / 2.0)
    SearchService-->>API: List of SearchResult (ranked descending by similarity)
    API-->>Frontend: SearchResponse (JSON)
    Frontend-->>User: Render ranked chunk cards with % match and #L{start}-L{end}
    User->>Frontend: Click "Open in Code Explorer"
    Frontend->>Explorer: Switch to Explorer tab, select file, and highlight lines
```

---

## 4. Knowledge Graph Construction & Traversal Flow (Phase 5 Completed)

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Frontend as React Dashboard (Graph Tab)
    participant API as FastAPI Graph Router (/repositories/{id}/graph)
    participant Traversal as GraphTraversalService
    participant Store as NetworkXGraphStore (DiGraph)
    participant Disk as Storage (storage/graphs/{id}.json)

    Note over API,Store: Indexing Stage 7: Graph Construction
    API->>Store: Build nodes & edges from ParsedRepository
    Store->>Disk: Atomic write to {id}.json.tmp -> {id}.json

    Note over User,Disk: User Graph Exploration & Traversal
    User->>Frontend: Select Knowledge Graph tab
    Frontend->>API: GET /api/v1/repositories/{id}/graph/status
    API->>Store: get_stats(repo_id)
    Store-->>Frontend: Node counts, edge counts, density

    User->>Frontend: Click symbol "authenticate_user" (Ego Subgraph)
    Frontend->>API: GET /api/v1/repositories/{id}/graph/subgraph?center_node_id=...&radius=1
    API->>Store: get_subgraph(center_node_id, radius=1, max_nodes=50)
    Store-->>Frontend: Subgraph JSON (nodes, edges, relationships)
    Frontend-->>User: Render interactive SVG radial layout with directed arrows

    User->>Frontend: Click "View Call Hierarchy"
    Frontend->>API: GET /api/v1/repositories/{id}/graph/callers?symbol=authenticate_user
    API->>Traversal: find_callers(repo_id, "authenticate_user")
    Traversal->>Store: Incoming CALLS edges
    Store-->>Frontend: Callers with line numbers, call frequency, and confidence

    User->>Frontend: Click "Calculate Blast Radius" (Impact Analysis)
    Frontend->>API: GET /api/v1/repositories/{id}/graph/impact?target=authenticate_user&depth=2
    API->>Traversal: analyze_impact(repo_id, "authenticate_user", depth=2)
    Traversal->>Store: Reverse BFS along incoming callers and dependents
    Store-->>Frontend: Impacted symbols, direct callers, and affected files list
```
```
