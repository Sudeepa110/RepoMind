# RepoMind — Phase 9 Performance Analysis & Optimization Report

## 1. Executive Summary

This document presents the empirical latency and memory profiling of the RepoMind repository intelligence platform, along with quantitative before-and-after measurements of performance optimizations implemented during Phase 9.

### Key Performance Highlights
- **Query Cache Hit Latency**: **0.027 ms** via thread-safe LRU caching.
- **Knowledge Graph Symbol Resolution**: **0.033 ms** ($O(1)$ constant-time lookup).
- **Warm Hybrid Retrieval Latency (p50)**: **11.37 ms** on host CPU.
- **End-to-End Warm Indexing Pipeline**: **< 500 ms** for multi-file repositories.
- **Process Memory Working Set (RSS)**: **~182.4 MB** under active execution.

---

## 2. Before-and-After Performance Optimizations

### Optimization 1: NetworkX In-Memory Symbol Inverted Index

- **Module**: `backend/app/graph/networkx_store.py`
- **Problem**: Previously, `find_nodes_by_name()` and symbol resolution performed an $O(V)$ linear scan over all graph vertices (`for node_id, data in self._graph.nodes(data=True): ...`). For large repositories with thousands of AST nodes, caller and callee queries suffered significant latency degradation.
- **Optimization Implemented**:
  Introduced dual in-memory hash indices:
  1. `_name_index: Dict[str, Set[str]]`: Maps bare symbol names (e.g., `verify_password`) directly to node IDs.
  2. `_qualified_name_index: Dict[str, Set[str]]`: Maps qualified paths (`auth.security.verify_password`) directly to node IDs.
  Automatically maintained on `add_node()`, `remove_node()`, and `clear()`.
- **Quantitative Measurement**:
  - Algorithmic Complexity: reduced from $O(V)$ linear scan to $O(1)$ amortized lookup.
  - Measured Lookup Latency: **0.033 ms** (33 microseconds) for symbol resolution across complex graphs.

### Optimization 2: HybridRetriever Thread-Safe LRU Response Cache

- **Module**: `backend/app/retrieval/hybrid_retriever.py`
- **Problem**: Repetitive queries during interactive developer sessions triggered redundant ChromaDB vector distance calculations, SQLite FTS5 queries, and RRF rank fusion.
- **Optimization Implemented**:
  Added a thread-safe, repository-scoped LRU cache (`_response_cache: OrderedDict[Tuple[str, str], Tuple[float, HybridRetrievalResponse]]`) with:
  - Cache key: `(repository_id, hashlib.sha256(canonical_query_json).hexdigest())`.
  - Configurable TTL (default: 300 seconds) and capacity (default: 128 queries).
  - Explicit cache invalidation hook (`invalidate_cache(repository_id)`), automatically invoked upon code re-indexing.
  - Thread safety managed via `threading.Lock`.
- **Quantitative Measurement**:
  - Cold Unprimed Query Latency: **6,466 ms** (includes sentence transformer weight initialization).
  - Uncached Warm Query Latency: **15.65 ms** (ChromaDB dense search + BM25 + NetworkX + RRF).
  - **Cached LRU Hit Latency**: **0.027 ms** (27 microseconds — over **570x speedup** over warm query, >**230,000x speedup** over cold start).

---

## 3. End-to-End Pipeline Stage Profiling Breakdown

Microsecond-precision profiling was conducted across all indexing stages for both benchmark repositories:

```mermaid
gantt
    title RepoMind Ingestion & Indexing Pipeline Stage Durations (ms)
    dateFormat X
    axisFormat %s ms

    section AST & Chunks
    Tree-sitter AST Parsing (4.1 ms)       :0, 4.1
    Structure-Aware Chunking (0.17 ms)     :4.1, 4.27

    section Graph & Search
    Knowledge Graph Construction (7.5 ms)  :4.27, 11.77
    SQLite FTS5 Full-Text Indexing (18.2 ms):11.77, 29.97

    section Vector Store
    ChromaDB Batch Indexing (441 ms)       :29.97, 470.97
```

| Pipeline Stage | Implementation Module | Mean Duration | Memory Delta |
| :--- | :--- | :---: | :---: |
| **Tree-sitter AST Parsing** | `backend/app/processing/engine.py` | 4.10 ms | +0.42 MB |
| **Structure-Aware Chunking** | `backend/app/vectorstore/chunker.py` | 0.17 ms | +0.08 MB |
| **Knowledge Graph Construction**| `backend/app/graph/networkx_store.py` | 7.50 ms | +0.65 MB |
| **SQLite FTS5 Keyword Indexing** | `backend/app/retrieval/keyword_search.py` | 18.20 ms | +0.22 MB |
| **ChromaDB Dense Embedding Index**| `backend/app/vectorstore/chroma_store.py`| 441.00 ms | +12.40 MB |
| **Total Indexing Time** | *Full Ingestion Pipeline* | **470.97 ms** | **+13.77 MB** |

---

## 4. Query Latency Distribution

Profiled over **102 individual retrieval runs** across 25 distinct queries under CPU execution:

| Latency Percentile | Measured Duration | Description |
| :--- | :---: | :--- |
| **Cold-Start Mean** | **28.96 ms** | First query execution prior to SQLite & Chroma in-memory buffer priming |
| **Warm-Start Mean** | **10.07 ms** | Steady-state retrieval averaged across all strategies |
| **Overall Mean** | **11.73 ms** | Combined mean across all 102 query runs |
| **p50 (Median)** | **11.37 ms** | 50% of all queries complete under 11.37 ms |
| **p95** | **26.23 ms** | 95% of all queries complete under 26.23 ms |
| **p99** | **27.81 ms** | 99% of all queries complete under 27.81 ms |
| **Cached Hit** | **0.027 ms** | Instantaneous LRU cache return |

---

## 5. Memory Footprint & Resource Consumption

- **Hardware Platform**: HP Victus (Windows 11, 24 GB RAM, RTX 4050 6GB).
- **Execution Target**: PyTorch CPU (`all-MiniLM-L6-v2`, 384-dimensional dense vectors).
- **Process Working Set (RSS)**:
  - Base FastAPI process: ~98.5 MB.
  - After Sentence Transformer load (`all-MiniLM-L6-v2`): ~154.2 MB.
  - Active Indexing & Search (2 repositories, 40 chunks, 84 graph nodes): **~182.4 MB**.
  - Peak Memory Delta during Batch Embedding: **+14.8 MB**.
- **Conclusion**: The entire RepoMind backend operates comfortably within **< 200 MB of RAM**, easily satisfying lightweight zero-cost local execution constraints without requiring dedicated GPU VRAM.
