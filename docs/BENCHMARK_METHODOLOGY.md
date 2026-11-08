# RepoMind — Phase 9 Benchmark Methodology

## 1. Objective and Scope

This document specifies the experimental setup, dataset provenance, query taxonomy, ground-truth annotation procedures, and runtime controls used to conduct empirical evaluations in RepoMind Phase 9.

The benchmark methodology ensures that all performance claims are **reproducible**, **statistically grounded**, and conducted on genuine codebase representations rather than simulated approximations.

---

## 2. Dataset Provenance and Specifications

The evaluation framework evaluates RepoMind across two distinct benchmark repositories:

### 2.1 Synthetic Benchmark Repository (`synthetic_auth_repo`)

A fully controlled, multi-tier Python authentication and session management application designed to verify structural relationship extraction, cross-file caller/callee resolution, and change impact blast radius.

- **Files**: 7 core Python modules:
  - `backend/auth/security.py`: Password hashing, HMAC generation, constant-time verification.
  - `backend/auth/jwt_handler.py`: JWT token creation, decoding, expiration validation.
  - `backend/database/models.py`: Declarative user, role, and session ORM models.
  - `backend/database/connection.py`: Database session pool and transaction context managers.
  - `backend/services/auth_service.py`: High-level credential verification and authentication flow.
  - `backend/api/auth_router.py`: REST endpoints (`/login`, `/register`, `/verify`, `/logout`).
  - `backend/config/settings.py`: Application environment settings and secret key management.
- **Complexity**:
  - Total Files: 7
  - Total Structure-Aware Chunks: 22
  - Knowledge Graph Nodes: 28 (classes, methods, functions)
  - Confirmed Structural Edges: 56 (`CALLS`, `DEFINES`, `IMPORTS`, `INHERITS`)
  - Unresolved External Calls: 15 (standard library / third-party modules: `hashlib`, `jwt`, `datetime`, `os`)

### 2.2 Real-World Open-Source Subset (`real_world_flask_subset`)

A real-world subset drawn from the widely-used `pallets/flask` production repository at commit `e559fa7` to verify scalability on complex production codebases with dynamic decorators, context managers, and meta-programming.

- **Origin**: `pallets/flask` (commit `e559fa7`, tag `3.0.0`).
- **Files**: 5 production modules:
  - `src/flask/app.py`: The central `Flask` WSGI application object, route registration, and dispatch.
  - `src/flask/blueprints.py`: Modular routing blueprint abstractions and deferred registration.
  - `src/flask/config.py`: Hierarchical dictionary-backed configuration container.
  - `src/flask/helpers.py`: Utility functions (`url_for`, `flash`, `send_file`).
  - `src/flask/ctx.py`: Application and request context stack management.
- **Complexity**:
  - Total Files: 5
  - Total Structure-Aware Chunks: 18
  - Total Lines of Code: ~2,400 LOC
  - Highly dynamic constructs: metaclasses, context locals, deferred callbacks, polymorphic dispatch.

---

## 3. Query Taxonomy & Intent Distribution

The evaluation benchmark includes **25 standardized developer queries** categorized across 14 distinct developer intents. Each query is annotated with ground-truth expected files, expected symbols, and line ranges.

| Category | Intent Description | Queries | Expected Target Strategy |
| :--- | :--- | :---: | :--- |
| **`EXACT_SYMBOL`** | Direct identifier or function signature lookup | 3 | Keyword / Graph |
| **`SEMANTIC`** | Conceptual, behavioral question without exact name | 3 | Vector / Hybrid |
| **`CALLERS`** | Reverse invocation lookup (who calls this function?) | 2 | Graph / Hybrid |
| **`CALLEES`** | Forward invocation lookup (what does this function call?) | 2 | Graph / Hybrid |
| **`DEPENDENCIES`** | File and module import coupling analysis | 2 | Graph |
| **`INHERITANCE`** | Class hierarchy, base classes, and overrides | 2 | Graph |
| **`EXECUTION_FLOW`** | Multi-hop cross-file execution path tracing | 2 | Graph / Hybrid |
| **`IMPACT_ANALYSIS`** | Blast radius and dependent component consequences | 2 | Graph / Hybrid |
| **`BUG_INVESTIGATION`** | Detection of unresolved calls or error handling bugs | 2 | Graph / Hybrid |
| **`ABSTAIN`** | Out-of-scope query testing honest abstention | 1 | Honest Refusal |
| **`INJECTION`** | Adversarial prompt override payload defense | 1 | Guardrail Defense |
| **`TEST_RECOMMENDATION`** | Automated test case generation for modified code | 1 | Hybrid + Intelligence |
| **`DOCUMENTATION`** | Architectural documentation and interface generation | 1 | Hybrid + Intelligence |
| **`ARCHITECTURE`** | High-level repository structure and entry point analysis | 1 | Hybrid |

---

## 4. Test Execution Controls & Hardware Rigor

To eliminate experimental bias and ensure reproducibility, all benchmarks adhere to strict execution controls:

1. **Hardware Specifications**:
   - Host Machine: HP Victus 15.
   - Operating System: Windows 11 Home (x86_64).
   - CPU: 13th Gen Intel Core i5 / AMD Ryzen (12 logical cores).
   - Memory: 24 GB DDR4/DDR5 RAM.
   - Dedicated GPU: NVIDIA GeForce RTX 4050 Laptop GPU (6 GB VRAM).
2. **Execution Mode**:
   - PyTorch CPU mode (`torch.device("cpu")`) is configured as the default execution target to ensure zero-cost reproducibility across developer environments without requiring CUDA.
3. **Network Isolation**:
   - Environment variables `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` prevent network access during sentence embedding generation, eliminating HTTP backoff delays.
4. **Latency Measurement**:
   - High-resolution timing via Python's `time.perf_counter()`.
   - Cold-start runs measured prior to database buffer cache priming.
   - Warm-start runs averaged over multiple iterations.
   - Percentiles computed using linear rank interpolation: p50 (median), p95, p99.
5. **Memory Measurement**:
   - Working set size (RSS) sampled via native Win32 `GetProcessMemoryInfo` API before and after each pipeline stage.

