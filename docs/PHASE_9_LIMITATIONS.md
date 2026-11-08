# RepoMind — Phase 9.2 Limitations, Boundaries & Evaluation Transparency

## 1. Overview

While Phase 9, Phase 9.1, and Phase 9.2 establish high empirical retrieval accuracy, calibrated hybrid rankings across Python, TypeScript, and Java, and sub-second warm indexing performance, several structural, computational, and algorithmic boundaries exist. This document provides a transparent technical disclosure of these boundaries.

---

## 2. Evaluation Framework & Dataset Transparency

### 2.1 Explicit Separation of Real-World and Synthetic Repositories
- **Real-World Repositories**:
  - `real_world_flask_subset` (Python, Pallets Flask commit `e559fa7`)
  - `real_world_ky_subset` (TypeScript, sindresorhus/ky commit `3541888`)
  - `real_world_petclinic_subset` (Java, spring-projects/spring-petclinic commit `500158f`)
  These represent authentic open-source library architectures with real-world complexity, imports, and design patterns.
- **Synthetic Repositories**:
  - `synthetic_auth_repo` (Python authentication microservice)
  - `synthetic_ts_express_repo` (TypeScript Express API)
  - `synthetic_java_petclinic_repo` (Java Spring domain model)
  These are controlled, deterministic test fixtures designed to stress specific language features (e.g., lowerCamelCase methods, interface implementations, exception handlers). They are explicitly identified as synthetic and never reported as real-world codebases.

### 2.2 Offline Citation Benchmarking vs Live LLM Generation
- **Offline Benchmark Nature**: In `backend/evaluation/benchmark_orchestrator.py`, synthetic claim templates (`"The symbol '{r.symbol_name}' is declared in [{r.file_path}:{r.start_line}-{r.end_line}]."`) are generated directly from retrieved code chunks.
- **Scope & Boundary**: This tests the citation extractor, interval overlap math (`calculate_line_overlap_iou()`), and range boundary validation with mathematical determinism (yielding 100% validity). It does **not** simulate stochastic LLM hallucination. Live conversational grounding against Gemini is evaluated separately in Phase 7 live integration suites (`tests/evaluation/test_grounding_evaluation.py`).

### 2.3 Honest Abstention Thresholds & Boundary Behaviors
- **Observed Behavior**: RepoMind achieved **66.7% abstention accuracy** across out-of-scope queries (e.g. querying for quantum stabilizers, blockchain smart contracts, RabbitMQ brokers, Kafka brokers in unrelated repositories).
- **Nuance**: In 2 out of 6 test cases (`Q40` on TypeScript Express and `Q54` on Spring PetClinic), dense semantic embeddings found weakly similar lexical matches in generic error handlers, resulting in marginal retrieval scores that passed the strict similarity cutoff. Improving semantic abstention requires continuous calibrating of the cosine distance threshold per language embedding distribution.

### 2.4 Adversarial Prompt Injection Defense
- **Offline Benchmark Nature**: Scans pre-sanitized generated text for known attack markers (`SYSTEM_PWNED_1234`, `LEAKED_KEY_XYZ`).
- **Scope & Boundary**: Verifies that if an injection marker is returned by a compromised generation, the validator detects it. It does not replace live red-teaming against frontier LLMs using novel jailbreak patterns.

### 2.5 Static Bug Investigation & Impact Analysis
- **Offline Benchmark Nature**: Evaluates against labeled synthetic AST fixtures in `synthetic_auth_repo` (`process_payment` containing unmapped references, `delete_account_endpoint` containing unhandled exceptions).
- **Scope & Boundary**: High precision and recall (1.00) apply strictly to AST-detectable structural anomalies. Static analysis cannot catch dynamic runtime exceptions, race conditions, memory leaks, or logical business flaws.

---

## 3. Code Analysis & Knowledge Graph Boundaries

### 3.1 Dynamic & Polymorphic Execution Resolution
- **Issue**: Tree-sitter is a static syntactic parser. Dynamic runtime behaviors cannot be fully resolved at indexing time without full abstract interpretation or symbolic execution.
- **Affected Constructs**:
  - Dynamic attribute access (`getattr(module, dynamic_name)()`).
  - Metaclasses and dynamic class construction (`type("DynamicClass", (), {})`).
  - Python dictionary dispatch tables mapping strings to functions.
  - Dependency injection containers and runtime factory registries.
- **Consequence**: In `real_world_flask_subset`, deferred blueprint callbacks and WSGI dispatcher wrappers cannot be connected to caller graphs statically, resulting in unresolved external edge markers.

### 3.2 Cross-File Import Aliasing & Star Imports
- **Issue**: Multi-hop star imports (`from module import *`) or deep relative alias chains (`from ...core.utils import helper as h`) require full workspace module resolution.
- **Current Behavior**: When an alias cannot be uniquely resolved to a specific file symbol, RepoMind records an unconfirmed edge with `resolution_status = "UNRESOLVED_CALL"` and structural confidence `0.5`, rather than hallucinating an invalid edge.

### 3.3 Multi-Language Parsing Depth Parity
- **Python**: Full AST visitor capturing classes, functions, async methods, decorators, and call hierarchies.
- **TypeScript**: AST visitor capturing classes, interfaces, lowerCamelCase methods, type aliases, and import paths. Overloaded function signatures and ambient declarations (`declare module`) are parsed syntactically but do not construct runtime type relationships.
- **Java**: AST visitor capturing classes, interfaces, method declarations, constructor invocations, and Spring annotations. Generic wildcard types and complex reflection invocations (`Class.forName(...)`) remain unresolved at the static graph level.
- **Non-AST Files**: Markdown, YAML, JSON, Dockerfiles, and shell scripts bypass GraphRAG and are indexed via Structure-Aware Chunking, ChromaDB dense embeddings, and SQLite BM25 full-text search.

---

## 4. Hardware, Performance & Scaling Limits

### 4.1 CPU Execution Limits on Large Repositories
- **Current Setup**: Optimized for zero-cost CPU execution using `sentence-transformers/all-MiniLM-L6-v2` on an HP Victus host.
- **Measured Throughput**:
  - Small repositories (< 50 files, < 200 chunks): **< 500 ms** total indexing time.
  - Large repositories (> 5,000 files, > 25,000 chunks): CPU batch embedding would require several minutes.
- **Recommendation**: For enterprise repositories, configure `torch.device("cuda")` with an NVIDIA GPU (such as the onboard RTX 4050 6GB) or deploy distributed worker queues.

### 4.2 In-Memory NetworkX Storage Boundaries
- **Current Setup**: Knowledge graphs are stored in memory using NetworkX directed multi-graphs (`MultiDiGraph`) and persisted to disk via Pickle.
- **Memory Consumption**: Approximately 0.65 MB per 100 graph nodes.
- **Upper Limit**: Suitable for repositories up to ~100,000 code entities (~500 MB RAM). Repositories exceeding 500,000 entities will require a distributed graph database backend (e.g., Neo4j or Memgraph).
