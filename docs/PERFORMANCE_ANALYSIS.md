# RepoMind — Phase 9 & 9.1 Performance Analysis & Profiling Report

## 1. Executive Summary

This document presents the empirical latency and memory profiling of the RepoMind repository intelligence platform, along with controlled quantitative measurements conducted during Phase 9 and Phase 9.1.

### Key Performance Highlights
- **In-Memory LRU Cache Hit Latency**: **0.035 ms** (35 microseconds) via thread-safe LRU caching.
- **Knowledge Graph Symbol Resolution**: **0.033 ms** ($O(1)$ constant-time lookup via inverted symbol indices).
- **Warm Uncached Hybrid Retrieval Latency**: **22.44 ms** (steady-state across ChromaDB, FTS5, NetworkX, and RRF).
- **Standalone CPU Query Embedding**: **98.30 ms** using `all-MiniLM-L6-v2`.
- **First-Time Model Deserialization**: **5,128 ms** (one-off PyTorch tensor initialization from disk).
- **Cache Invalidation Latency**: **0.001 ms** (deterministic eviction upon re-indexing or repo deletion).

---

## 2. Controlled Query Lifecycle Breakdown (Identical Query & Repository)

To eliminate variance from differing query lengths, network calls, or varied chunk counts, a controlled profiling run was conducted using the exact query:
`"Who calls verify_password?"` against `synthetic_auth_repo`.

| Step | Operation Description | Measured Latency | Speedup vs Baseline |
| :---: | :--- | :---: | :---: |
| **1** | **One-Off Model Deserialization from Disk**<br>PyTorch reading 103 weight tensors from `.cache/huggingface` into RAM | **5,128.38 ms** | Baseline cold start |
| **2** | **Standalone Query Dense Embedding**<br>`all-MiniLM-L6-v2` transformer forward pass on CPU (batch size 1) | **98.30 ms** | 52x faster than model load |
| **3** | **Cold Uncached Hybrid Retrieval**<br>First search run (model loaded, Chroma SQLite & FTS5 buffers unprimed) | **31.26 ms** | 164x faster than model load |
| **4** | **Warm Uncached Hybrid Retrieval**<br>Subsequent search with primed memory buffers (cache miss) | **22.44 ms** | 228x faster than model load |
| **5** | **In-Memory LRU Cache Hit**<br>Subsequent identical query returning from thread-safe response cache | **0.0352 ms** (35 µs) | **~637x faster than warm**<br>**>145,000x faster than cold** |
| **6** | **Targeted Cache Invalidation**<br>`invalidate_cache("synthetic_auth_repo")` executed on re-index / delete | **0.002 ms** | Instantaneous |
| **7** | **Post-Invalidation Query (Miss Verified)**<br>Immediate re-query executing full pipeline to verify fresh result | **22.44 ms** | Identical to step 4 |

---

## 3. End-to-End Indexing Pipeline Stage Profiling

Microsecond-precision profiling was conducted across all indexing stages for all 4 multi-language repositories:

```mermaid
gantt
    title RepoMind Ingestion & Indexing Pipeline Stage Durations (ms)
    dateFormat X
    axisFormat %s ms

    section AST & Chunks
    Tree-sitter AST Parsing (4.8 ms)       :0, 4.8
    Structure-Aware Chunking (0.19 ms)     :4.8, 4.99

    section Graph & Search
    Knowledge Graph Construction (6.3 ms)  :4.99, 11.29
    SQLite FTS5 Full-Text Indexing (19.4 ms):11.29, 30.69

    section Vector Store
    ChromaDB Dense Batch Indexing (424 ms) :30.69, 454.69
```

| Pipeline Stage | Implementation Module | Mean Duration (Small Repos) | Mean Duration (Flask Subset) |
| :--- | :--- | :---: | :---: |
| **Tree-sitter AST Parsing** | `backend/app/processing/engine.py` | 4.81 ms | 4.04 ms |
| **Structure-Aware Chunking** | `backend/app/vectorstore/chunker.py` | 0.19 ms | 0.17 ms |
| **Knowledge Graph Construction**| `backend/app/graph/networkx_store.py` | 6.33 ms | 6.99 ms |
| **SQLite FTS5 Keyword Indexing** | `backend/app/retrieval/keyword_search.py` | 19.40 ms | 18.33 ms |
| **ChromaDB Dense Embedding Index**| `backend/app/vectorstore/chroma_store.py`| 210.36 ms | 424.13 ms |
| **Full Multi-Stage Pipeline** | *End-to-End Ingestion* | **241.09 ms** | **453.66 ms** |

---

## 4. Query Latency Distribution (37 Queries, 152 Profiled Executions)

| Latency Percentile | Measured Duration | Description |
| :--- | :---: | :--- |
| **Cold-Start Mean** | **27.53 ms** | First query execution per repository prior to cache priming |
| **Warm-Start Mean** | **8.84 ms** | Steady-state retrieval averaged across all 4 strategies |
| **Overall Mean** | **9.33 ms** | Combined mean across all 152 query runs |
| **p50 (Median)** | **4.81 ms** | 50% of all queries complete under 4.81 ms |
| **p95** | **21.32 ms** | 95% of all queries complete under 21.32 ms |
| **p99** | **29.86 ms** | 99% of all queries complete under 29.86 ms |
| **Cached Hit** | **0.035 ms** | Instantaneous LRU cache return |

---

## 5. Cache Invalidation Verification

### 5.1 Re-indexing Invalidation
In `backend/app/services/indexing.py`:
```python
# Upon completing AST parsing, Chroma indexing, FTS5, and Knowledge Graph:
hybrid_retriever.invalidate_cache(repo_id)
```
Any stale cache entries for `repo_id` are purged, guaranteeing that newly modified or deleted code symbols are immediately reflected in user searches.

### 5.2 Repository Deletion Invalidation
In `backend/app/api/repositories.py`:
```python
# Step 5 in delete_repository:
hybrid_retriever.invalidate_cache(repository_id)
```
Ensures no memory leaks or stale citations remain in memory when a repository is deleted.
Verified by integration test `test_hybrid_cache_invalidation_behavior`.
