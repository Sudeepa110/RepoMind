# RepoMind — Phase 9.2 Performance Analysis & Multi-Language Profiling Report

## 1. Executive Summary

This document presents empirical latency, memory profiling, and throughput metrics for the RepoMind repository intelligence platform across all **6 multi-language benchmark repositories** following the completion of **Phase 9.2: Cross-Language Retrieval Validation & Final Quality Gate**.

### Key Performance Highlights
- **In-Memory LRU Cache Hit Latency**: **0.035 ms** (35 microseconds) via thread-safe LRU caching.
- **Knowledge Graph Symbol Resolution**: **0.033 ms** ($O(1)$ constant-time lookup via inverted symbol indices).
- **Warm Uncached Hybrid Retrieval Latency**: **11.86 ms – 14.81 ms** across Python, TypeScript, and Java.
- **Fastest Single-Engine Retrieval (BM25 & Graph)**: **0.73 ms – 2.67 ms** (NetworkX and SQLite FTS5).
- **Total Indexing Time (Real-World Repos)**:
  - `real_world_flask_subset`: **335.3 ms**
  - `real_world_ky_subset`: **247.5 ms**
  - `real_world_petclinic_subset`: **647.4 ms**
- **Targeted Cache Invalidation Latency**: **0.002 ms** (instantaneous eviction upon re-indexing or repo deletion).

---

## 2. End-to-End Indexing Pipeline Stage Profiling (All 6 Repositories)

Microsecond-precision profiling was recorded across all indexing stages for both real-world and synthetic repositories:

| Repository Identifier | Language | Files / Chunks | Tree-sitter Parsing | Chunk Generation | ChromaDB Vector Index | SQLite FTS5 Index | NetworkX Graph Build | Total Indexing Duration |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`synthetic_auth_repo`** | Python | 7 / 22 | 2.90 ms | 0.11 ms | 511.25 ms | 14.52 ms | 5.22 ms | **534.00 ms** |
| **`real_world_flask_subset`** | Python | 5 / 18 | 2.44 ms | 0.10 ms | 312.94 ms | 14.21 ms | 5.57 ms | **335.26 ms** |
| **`synthetic_ts_express_repo`**| TypeScript | 5 / 9 | 2.07 ms | 0.08 ms | 98.19 ms | 14.81 ms | 4.57 ms | **119.72 ms** |
| **`real_world_ky_subset`** | TypeScript | 5 / 15 | 8.39 ms | 0.15 ms | 218.47 ms | 13.66 ms | 6.88 ms | **247.55 ms** |
| **`synthetic_java_petclinic_repo`**| Java | 5 / 15 | 3.33 ms | 0.15 ms | 150.04 ms | 13.37 ms | 4.89 ms | **171.78 ms** |
| **`real_world_petclinic_subset`**| Java | 6 / 36 | 11.24 ms | 0.48 ms | 604.96 ms | 16.26 ms | 14.48 ms | **647.42 ms** |

```mermaid
gantt
    title RepoMind End-to-End Indexing Pipeline Duration (Real-World PetClinic: 647 ms)
    dateFormat X
    axisFormat %s ms

    section AST & Chunks
    Tree-sitter Java Parsing (11.2 ms)     :0, 11.2
    Structure-Aware Chunking (0.5 ms)      :11.2, 11.7

    section Graph & Search
    Knowledge Graph Build (14.5 ms)        :11.7, 26.2
    SQLite FTS5 Full-Text Index (16.3 ms)  :26.2, 42.5

    section Vector Store
    ChromaDB Dense Batch Indexing (605 ms) :42.5, 647.5
```

---

## 3. Query Latency Distribution (54 Queries, 222 Profiled Executions)

Aggregated system query profiling across all 4 retrieval strategies and 6 repositories:

| Latency Percentile / Metric | Measured Duration | Description |
| :--- | :---: | :--- |
| **Cold-Start Mean** | **18.63 ms** | First query execution per repository prior to buffer priming |
| **Warm-Start Mean** | **7.02 ms** | Steady-state retrieval averaged across all 4 strategies |
| **Overall Mean** | **7.33 ms** | Combined mean across all 222 query runs |
| **p50 (Median)** | **5.47 ms** | 50% of all queries complete under 5.47 ms |
| **p95** | **18.45 ms** | 95% of all queries complete under 18.45 ms |
| **p99** | **21.93 ms** | 99% of all queries complete under 21.93 ms |
| **Cached Hit (LRU)** | **0.035 ms** | Instantaneous memory cache return |

---

## 4. Controlled Strategy-by-Strategy Latency Comparison

Measured across warm uncached query runs:

| Retrieval Strategy | Mean Latency | p50 Latency | Dominant Bottleneck |
| :--- | :---: | :---: | :--- |
| **Graph-Only (NetworkX)** | **1.64 ms** | **1.21 ms** | In-memory adjacency list lookups |
| **Keyword-Only (BM25)** | **1.89 ms** | **1.94 ms** | SQLite FTS5 inverted token matching |
| **Vector-Only (ChromaDB)** | **11.33 ms** | **10.95 ms** | MiniLM-L6 dense query transformer forward pass on CPU |
| **Hybrid (Fused RRF)** | **13.32 ms** | **13.91 ms** | Parallel Vector + Graph + BM25 dispatch and RRF score normalization |

---

## 5. Multi-Tenant Security & Cache Isolation Verification

Integration test `test_hybrid_cross_repository_isolation` (`tests/integration/test_hybrid_retrieval.py`) confirmed:

1. **Storage Tenant Filtering**:
   - ChromaDB `collection.query(where={"repo_id": repo_id})` guarantees 0 cross-repository chunk exposure.
   - SQLite FTS5 `WHERE repo_id = ?` query isolation guarantees zero search cross-contamination.
2. **Response Cache Separation**:
   - Cache keys are prefixed with `repo_id`. Queries for the same term on separate repositories evaluate as independent cache entries.
3. **Cache Invalidation Latency**:
   - Calling `hybrid_retriever.invalidate_cache(repo_id)` completes in **0.002 ms** and deterministically purges only the target repository's cached entries.
