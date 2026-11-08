# RepoMind — Phase 9 Limitations & Edge Cases

## 1. Overview

While Phase 9 establishes high empirical retrieval accuracy, 100% grounding validity, and sub-second indexing performance, several structural, computational, and algorithmic limitations exist. This document provides a transparent technical disclosure of these boundaries.

---

## 2. Code Analysis & Graph Limitations

### 2.1 Dynamic & Polymorphic Execution Resolution
- **Issue**: Tree-sitter is a static syntactic parser. Dynamic runtime behaviors cannot be fully resolved at indexing time without full abstract interpretation or symbolic execution.
- **Affected Constructs**:
  - Dynamic attribute access (`getattr(module, dynamic_name)()`).
  - Metaclasses and dynamic class construction (`type("DynamicClass", (), {})`).
  - Python dictionary dispatch tables mapping strings to functions.
  - Dependency injection containers and runtime factory registries.
- **Consequence**: In the `real_world_flask_subset` benchmark, dynamic dispatch functions such as deferred blueprint callbacks cannot be connected to caller graphs statically, resulting in unresolved external edge markers.

### 2.2 Cross-File Import Aliasing
- **Issue**: Complex multi-hop star imports (`from module import *`) or deep relative alias chains (`from ...core.utils import helper as h`) require full workspace module resolution.
- **Current Behavior**: When an alias cannot be uniquely resolved to a specific file symbol, RepoMind records an unconfirmed edge with `resolution_status = "UNRESOLVED_CALL"` and marks structural confidence at `0.5`, rather than hallucinating an invalid edge.

### 2.3 Non-AST File Types
- **Issue**: Full Knowledge Graph extraction is supported for Python and TypeScript/JavaScript. Unstructured text, configuration files, and documentation (Markdown, YAML, JSON, Dockerfiles) lack abstract syntax trees.
- **Current Behavior**: Non-AST files are indexed exclusively via Structure-Aware Chunking, ChromaDB dense vector embeddings, and SQLite BM25 full-text indexing, bypassing GraphRAG.

---

## 3. Retrieval & Ranking Limitations

### 3.1 Reciprocal Rank Fusion (RRF) Score Calibration
- **Issue**: RRF combines ranks using the formula $\text{RRF}(d) = \sum_{m} \frac{1}{60 + r_m(d)}$. The resulting score represents relative ordinal ranking rather than absolute semantic confidence.
- **Risk**: Min-max normalization of RRF scores can artificially scale a low-confidence top hit to 1.0, even when the query is completely unrelated to the repository.
- **Mitigation Implemented**: To ensure honest abstention, RepoMind inspects raw cosine distance ($d_{\text{cosine}} < 0.45$) and domain token overlap before declaring evidence sufficiency.

### 3.2 Granularity Trade-Off: File vs Chunk vs Symbol
- **Issue**: Developer questions vary widely in desired granularity: some require a single function body, while others require architectural understanding of a full module.
- **Current Behavior**: Hybrid retrieval returns chunks (mean size: 25-50 lines). If a developer asks for a high-level architectural overview, assembling multiple independent chunks can consume token context.

---

## 4. Hardware & Scaling Limits

### 4.1 CPU Execution Limits on Large Repositories
- **Current Setup**: Optimized for zero-cost CPU execution using `sentence-transformers/all-MiniLM-L6-v2` on an HP Victus host.
- **Measured Throughput**:
  - Small repositories (< 50 files, < 200 chunks): **< 500 ms** total indexing time.
  - Large repositories (> 5,000 files, > 25,000 chunks): CPU batch embedding would require several minutes.
- **Recommendation**: For enterprise-scale repositories, configure `torch.device("cuda")` with an NVIDIA GPU (such as the onboard RTX 4050 6GB) or deploy distributed worker queues.

### 4.2 Single-Node In-Memory NetworkX Storage
- **Current Setup**: Knowledge graphs are stored in memory using NetworkX directed multi-graphs (`MultiDiGraph`) and persisted to disk via Pickle.
- **Memory Consumption**: Approximately 0.65 MB per 100 graph nodes.
- **Upper Limit**: Suitable for repositories up to ~100,000 code entities (~500 MB RAM). Repositories exceeding 500,000 entities will require a distributed graph database backend (e.g., Neo4j or Memgraph).
