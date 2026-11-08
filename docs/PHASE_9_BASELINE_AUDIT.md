# RepoMind — Phase 9 Baseline Audit

**Date**: 2026-11-08  
**Hardware Environment**: HP Victus, 24 GB RAM, NVIDIA GeForce RTX 4050 Laptop GPU (6 GB VRAM)  
**Software Environment**: Windows 11, Python 3.11.9 (CPU-default PyTorch 2.15.0+cpu), Node.js v20+, Tree-sitter, ChromaDB 0.6.3, NetworkX 3.4.2  
**Starting Commit**: `f09c325` (Phase 8 Complete)  
**Baseline Test Status**: 130 / 130 tests passing (100.0%) in 42.90s  
**Baseline Frontend Build**: 0 errors, 393ms  

---

## 1. Existing System Architecture (Phases 1–8)

RepoMind currently integrates a dual-pipeline architecture:
1. **Phase 1 & 2 (Foundation & Ingestion)**: FastAPI backend, SQLite metadata via SQLAlchemy, shallow Git cloning with depth=1, size bounds (50MB/1000 files), SSRF validation, and `.gitignore`/binary exclusion.
2. **Phase 3 (Tree-sitter Parsing)**: Multi-language AST parsing (Python, TypeScript, JavaScript, Java, C, C++, Go) extracting unified symbols, calls, imports, and definitions with exact line ranges.
3. **Phase 4 (Vector RAG)**: Structure-aware chunking (`to_code_chunks`), `sentence-transformers/all-MiniLM-L6-v2` dense embeddings, persistent ChromaDB collections.
4. **Phase 5 (Knowledge Graph)**: In-memory & JSON-persisted NetworkX `DiGraph` storing `GraphNode` and `GraphEdge` entities with relations (`CONTAINS`, `IMPORTS`, `CALLS`, `INHERITS`, `IMPLEMENTS`, `DEPENDS_ON`), confidence scores, and resolution status (`CONFIRMED`, `INFERRED`, `UNRESOLVED`).
5. **Phase 6 (Hybrid Retrieval Engine)**: Rule-based `QueryAnalyzer`, strategy router, parallel multi-engine retrieval (Vector, Graph, Keyword SQLite FTS5), Reciprocal Rank Fusion (`RRF k=60`), and structured `ContextAssembler`.
6. **Phase 7 (Gemini LLM & Grounded Chat)**: Official `google-genai` SDK (`gemini-2.5-flash`), anti-prompt-injection boundary, `CitationValidator` verifying inline `[file:line-line]` citations, and SSE streaming chat.
7. **Phase 8 (Advanced Intelligence)**: Change impact analyzer (bounded BFS), execution flow tracer, Robert C. Martin instability coupling analyzer, evidence-backed bug investigator, deterministic risk assessor, test recommender, and technical documentation generator.

---

## 2. Existing Evaluation Coverage & Limitations

### Existing Tests
- `tests/evaluation/test_grounding_evaluation.py`: Evaluated 10 questions on a single synthetic repository.
- `tests/evaluation/test_hybrid_evaluation.py`: Evaluated hybrid retrieval on 7 synthetic queries.
- `tests/evaluation/test_retrieval_metrics.py`: Evaluated Precision@k, Recall@k, and MRR functions on synthetic lists.
- `tests/evaluation/test_intelligence_evaluation.py`: Evaluated impact precision/recall, risk monotonicity, and citation validity on a synthetic 5-node graph.

### Existing Limitations
1. **Lack of Graph-Only Baseline**: Phase 6 evaluated Vector-only, Keyword-only, and Hybrid, but did **not** run an independent Graph-only retrieval baseline across all queries.
2. **No Real Open-Source Repositories**: All previous benchmarks ran on small synthetic in-memory fixtures. No evaluation exists on real-world repositories with multi-directory structures, real imports, and real commit histories.
3. **Absence of nDCG@k Metric**: Retrieval metrics only measured Precision and Recall; graded ranking relevance (nDCG@5) was absent.
4. **Citation Validity vs. Citation Coverage**: Phase 7 measured syntactic citation validity (whether cited lines exist in evidence), but did not measure claim-level citation coverage (what fraction of factual claims have supporting citations).
5. **Prompt Injection Testing**: Untrusted prompt boundaries were designed, but no automated adversarial injection benchmark was executed against malicious code comments or READMEs.
6. **Bug Detection False Positive Rate**: Bug heuristics ran without a labeled ground-truth dataset measuring precision, recall, and false positive rates.

---

## 3. Existing Performance Measurement Coverage & Limitations

### Existing Capabilities
- Hybrid search logs total execution latency and per-engine duration (Vector, Graph, Keyword).
- Chat streaming emits retrieval latency and total generation latency.

### Existing Bottlenecks & Gaps
1. **No End-to-End Indexing Profiling**: No breakdown of time spent across clone, file discovery, tree-sitter parsing, embedding computation, ChromaDB insertion, FTS5 insertion, and graph construction.
2. **No Cold-Start vs. Warm-Start Differentiation**: First query triggers model loading and collection instantiation; subsequent queries benefit from memory caches, but this was never quantified.
3. **Query Latency Percentiles**: No p50, p95, p99 measurements under sustained query load.
4. **Hardware Resource Tracking**: Memory (RAM) consumption, CPU utilization, and GPU utilization during ingestion were not systematically monitored.
5. **Redundant Graph Serialization**: `networkx_graph_store` saves full JSON to disk on every modification; repeated queries re-scan all nodes if not cached.

---

## 4. Known Accuracy Limitations

1. **Static Analysis Horizon**: Tree-sitter extracts AST-resolvable references. Dynamic dispatch, runtime reflection, dependency injection, and `getattr` remain `UNRESOLVED` or `INFERRED`.
2. **Granularity Mismatch**: Vector chunks cover code blocks (e.g. 20–80 lines); keyword search matches identifiers; graph nodes represent individual symbols. Fusion across differing spatial granularities can dilute top-1 precision if weights are imbalanced.
3. **Broad Heuristics in Bug Investigation**: Unguarded public API handlers are flagged as `LOW` severity bugs even when protected by global FastAPI middleware, generating potential false positives.

---

## 5. Proposed Phase 9 Implementation Plan

1. **Reproducible Benchmark Dataset (`backend/evaluation/datasets/`)**:
   - Small synthetic repositories with unambiguous ground truth.
   - Real-world open-source repositories:
     - `pallets/flask` (or small core subset/commit `e559fa7`)
     - `psf/requests` (or small core subset/commit `b75225f`)
     - `encode/starlette` (or small core subset)
   - Cached local repository fixtures to prevent external network dependencies.
   - Ground-truth files, line ranges, symbols, relationships, and abstain queries.
2. **4-Way Retrieval Benchmarking**:
   - Independent evaluation of:
     1. Vector-only
     2. Keyword-only
     3. Graph-only (mandatory)
     4. Hybrid retrieval (RRF)
   - Measure: Precision@1, Precision@3, Precision@5, Recall@3, Recall@5, MRR, nDCG@5, exact symbol accuracy, file path accuracy.
3. **Citation & Grounded Answer Evaluation**:
   - Measure citation validity vs. citation coverage separately.
   - Test adversarial prompt injection resilience.
   - Test unanswerable queries (abstention).
4. **Graph & Intelligence Quality Evaluation**:
   - Labeled benchmark for impact analysis (precision, recall, false positive/negative rates).
   - Labeled bug detection dataset (unresolved calls, error handling, null safety).
   - Test recommendation relevance and documentation accuracy rubric.
5. **Profiling & Benchmarking Framework (`backend/evaluation/profiler.py`)**:
   - Measure durations across all 11 indexing stages.
   - Record memory (RSS), CPU %, query latency p50/p95/p99, cold vs. warm start.
6. **Evidence-Based Performance Optimizations**:
   - Target bottlenecks discovered during profiling (e.g. embedding batch size, in-memory graph index caching, query caching).
   - Provide strict before-and-after measurements for every optimization.
7. **Frontend Performance & Benchmark Dashboard**:
   - Display real benchmark metrics, retrieval comparison tables, and hardware specs without hardcoded simulation.

