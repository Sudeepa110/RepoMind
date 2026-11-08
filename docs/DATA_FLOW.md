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

---

## 5. Hybrid Retrieval & Context Assembly Flow (Phase 6 Completed)

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Frontend as React Dashboard (Hybrid Search)
    participant API as FastAPI Router (/repositories/{id}/hybrid-search)
    participant Retriever as HybridRetriever
    participant Analyzer as QueryAnalyzer
    participant Router as QueryRouter
    participant Vector as SemanticSearchService (ChromaDB)
    participant Keyword as KeywordSearchEngine (SQLite FTS5)
    participant Graph as GraphTraversalService (NetworkX)
    participant Fusion as ResultFusion (RRF k=60)
    participant Assembler as ContextAssembler

    User->>Frontend: Enter query: "who calls verify_token in this project?"
    Frontend->>API: POST /api/v1/repositories/{id}/hybrid-search
    API->>Retriever: hybrid_search(repo_id, request)

    Note over Retriever,Analyzer: 1. Deterministic Query Analysis
    Retriever->>Analyzer: analyze(query)
    Analyzer-->>Retriever: Intents: [CALLERS], Symbols: ["verify_token"]

    Note over Retriever,Router: 2. Strategy Plan Routing
    Retriever->>Router: route(analysis, top_k)
    Router-->>Retriever: Plan (Graph + Keyword + Vector enabled, weights: Graph 1.8)

    Note over Retriever,Graph: 3. Multi-Engine Retrieval & Traversal
    par Parallel Vector Search
        Retriever->>Vector: search(query) -> dense semantic chunks
    and Parallel Keyword Search
        Retriever->>Keyword: search(query) -> BM25 identifier matches
    and Parallel Graph Traversal
        Retriever->>Graph: find_callers(repo_id, "verify_token")
        Graph-->>Retriever: Caller relations: login, authorize [CONFIRMED]
        Retriever->>Keyword: Lookup chunks for caller symbols
    end

    Note over Retriever,Fusion: 4. Reciprocal Rank Fusion & Deduplication
    Retriever->>Fusion: fuse_and_rank(vector, keyword, graph, k=60, weights)
    Fusion-->>Retriever: Deduplicated results with RRF scores & engine badges

    Note over Retriever,Assembler: 5. Context Assembly
    Retriever->>Assembler: assemble(query, ranked_results, graph_evidence)
    Assembler-->>Retriever: Structured Markdown evidence + Verified citations table

    Retriever-->>API: HybridRetrievalResponse
    API-->>Frontend: JSON with execution times, intents, graph evidence & chunks
    Frontend-->>User: Render strategy badges, RRF scores, code snippets & citations
```

---

## 4. Phase 7: Conversational Grounded Query Flow & Streaming SSE

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Frontend as React Chat Dashboard
    participant API as FastAPI Router (/repositories/{id}/chat/stream)
    participant GenService as GenerationService
    participant ConvService as ConversationService
    participant SQLite as SQLite DB (Conversations & Messages)
    participant Retriever as HybridRetriever (Phase 6 Engine)
    participant Gemini as Google Gemini (gemini-2.5-flash)
    participant Validator as CitationValidator

    User->>Frontend: Submit question in active chat session
    Frontend->>API: POST /api/v1/repositories/{id}/chat/stream (SSE)
    API->>GenService: stream_answer(repository_id, request)

    GenService->>API: event: retrieval_started
    API-->>Frontend: Stream: retrieval_started
    
    GenService->>ConvService: add_message(role='user', content=query)
    ConvService->>SQLite: Persist user message & update title

    Note over GenService,Retriever: Execute Hybrid Retrieval (Phase 6 Pipeline)
    GenService->>Retriever: hybrid_search(repo_id, request)
    Retriever-->>GenService: HybridRetrievalResponse (Chunks + Graph Evidence)

    GenService->>API: event: retrieval_completed
    API-->>Frontend: Stream: retrieval_completed (chunks, latency, intents)

    Note over GenService: Evidence Sufficiency Evaluation
    alt NO_EVIDENCE
        GenService->>API: event: generation_started
        GenService->>API: event: token ("The indexed repository does not contain sufficient evidence...")
        GenService->>ConvService: add_message(role='assistant', insufficient=True)
        GenService->>API: event: done
        API-->>Frontend: Stream: done (0% hallucination)
    else SUFFICIENT or PARTIAL
        GenService->>API: event: generation_started
        Note over GenService,Gemini: Build Prompt with Untrusted Data Boundary
        GenService->>Gemini: generate_stream(prompt, system_instruction)
        
        loop Token Streaming
            Gemini-->>GenService: Yield token chunk
            GenService->>API: event: token (chunk)
            API-->>Frontend: Render streaming text in real-time
        end

        Note over GenService,Validator: Citation Validation against Ground Truth
        GenService->>Validator: validate_citations(full_text, retrieved_chunks, graph_evidence)
        Validator-->>GenService: Validated & verified citations list
        
        loop Emit Citations
            GenService->>API: event: citation (validated coordinates)
            API-->>Frontend: Render verified citation pill
        end

        GenService->>ConvService: add_message(role='assistant', content, citations)
        ConvService->>SQLite: Persist assistant message

        GenService->>API: event: done (metrics, latencies, confidence)
        API-->>Frontend: Stream: done
    end
```

---

## 5. Phase 8: Advanced Repository Intelligence & Multi-File Change Impact Analysis Flow

```mermaid
sequenceDiagram
    autonumber
    actor Developer
    participant UI as React Intelligence Workspace
    participant API as FastAPI Intelligence Router (/repositories/{id}/intelligence/...)
    participant Orch as IntelligenceOrchestrator
    participant Impact as ChangeImpactAnalyzer
    participant Flow as ExecutionFlowTracer
    participant Dep as DependencyAnalyzer
    participant Bug as BugInvestigator
    participant Risk as RiskAssessor
    participant Graph as NetworkX Knowledge Graph
    participant Gemini as Google Gemini
    participant Val as CitationValidator

    Developer->>UI: Select Analysis Mode (Impact / Flow / Bugs / Risk / Tests / Docs)
    Developer->>UI: Input Target Symbol or Entry Point
    UI->>API: POST /api/v1/repositories/{id}/intelligence/{sub_tool}
    API->>Orch: Dispatch to Specialized Intelligence Service

    alt Change Impact Analysis
        Orch->>Impact: analyze(repo_id, request)
        Impact->>Graph: Bounded BFS Traversal along CALLS & IMPORTS (max_depth=3)
        Graph-->>Impact: Direct callers, indirect propagation, structural parents
        Impact->>Risk: calculate_risk(direct, indirect, affected_files, is_api, is_model)
        Risk-->>Impact: Deterministic RiskScore (0-100) & Breakdown
        Impact->>Gemini: Synthesize explanation with citations [file:start-end]
        Gemini-->>Impact: Generated markdown
        Impact->>Val: validate_citations(text, evidence_chunks)
        Val-->>Impact: Verified citations
        Impact-->>Orch: ImpactAnalysisResult
    else Execution Flow Tracing
        Orch->>Flow: trace_flow(repo_id, request)
        Flow->>Graph: Traverse outgoing CALLS edges across file boundaries
        Graph-->>Flow: Ordered steps with crosses_file, branch points, external libs
        Flow->>Val: validate_citations(step_text, evidence_chunks)
        Flow-->>Orch: ExecutionFlowResult
    else Architectural Coupling
        Orch->>Dep: analyze(repo_id)
        Dep->>Graph: Calculate in-degree, out-degree, Martin's instability (I)
        Dep-->>Orch: DependencyAnalysisResult (layers, coupled pairs, external libs)
    else Bug Investigation
        Orch->>Bug: investigate(repo_id, request)
        Bug->>Graph: Scan unresolved calls, unguarded API handlers
        Bug-->>Orch: BugInvestigationResult (findings, severity, remediation)
    end

    Orch-->>API: Intelligence Result Payload
    API-->>UI: JSON Response
    UI-->>Developer: Render interactive metrics, step flow, risk gauge, findings & verified citation links
```

