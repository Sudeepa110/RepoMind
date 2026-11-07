# Evaluation Framework: Vector RAG, GraphRAG & Hybrid Retrieval

## Overview

RepoMind evaluates its retrieval and generation subsystems both independently and in hybrid combination across real-world open-source repositories.

---

## 1. Subsystem Evaluation Targets

### A. Vector RAG Evaluation
- **Target**: Semantic precision and conceptual grounding.
- **Metrics**:
  - `Context Precision@K`: Proportion of retrieved chunks directly relevant to the user query.
  - `Context Recall`: Verification that the core implementation method/class is captured in top-K context.
  - `Chunk Boundary Integrity`: Ensure chunks do not cut syntax structures in half.

### B. GraphRAG Evaluation
- **Target**: Structural connectivity, invocation chains, and dependency resolution.
- **Metrics**:
  - `Relationship Retrieval Accuracy`: Verified ratio of true static function calls vs. extracted edges.
  - `Caller/Callee Completeness`: Verification that all direct callers of a target function are identified.
  - `Impact Analysis Precision`: Identification of genuinely affected components when modifying a class/method without false positives.

### C. Hybrid Retrieval Evaluation
- **Target**: Cross-cutting queries (e.g. "Explain the complete login execution flow").
- **Metrics**:
  - `End-to-End Answer Correctness`: Ground-truth alignment verified by human inspection.
  - `Citation Accuracy`: Percentage of cited files and line numbers that accurately match source coordinates.
  - `Hallucination Rate`: Zero-tolerance target (0%) for non-existent methods, files, or arguments.
  - `Response Latency`: Time to first token (TTFT) and total generation time.
  - `Resource Consumption`: RAM usage (target < 4 GB) and GPU memory utilization.

---

## 2. Benchmark Repositories & Test Cases

| Repository | Query Type | Question | Expected Ground Truth |
|---|---|---|---|
| `fastapi/fastapi` | Vector RAG | "Explain how FastAPI handles dependency injection." | `fastapi/params.py:Depends`, `fastapi/dependencies/models.py` |
| `fastapi/fastapi` | GraphRAG | "Which functions call request_response()?" | Graph traversal matching callers in `fastapi/routing.py` |
| `pallets/flask` | Hybrid | "What happens when app.run() is called?" | Traversal of `app.py:run` calling `werkzeug.serving:run_simple` + snippet citations |
| `pmndrs/zustand` | GraphRAG | "What depends on createStore?" | Graph callers and import hierarchy across `src/vanilla.ts` and `src/react.ts` |
| `pallets/flask` | Impact Analysis | "What could be affected if I change Flask.dispatch_request?" | Identifies route handlers, `full_dispatch_request`, and view functions |
