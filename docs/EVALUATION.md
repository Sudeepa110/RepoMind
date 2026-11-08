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

---

## 3. Phase 4 Ground-Truth Evaluation Benchmark Results

Automated benchmark evaluation executed via `tests/evaluation/test_retrieval_metrics.py`:

| Metric | Target Threshold | Measured Score | Status |
|---|---|---|---|
| **Precision@1** | $\ge 80.0\%$ | **100.00%** | PASS |
| **Precision@3** | $\ge 35.0\%$ | **38.89%** | PASS |
| **Recall@3** | $\ge 85.0\%$ | **100.00%** | PASS |
| **Line Citation Accuracy** | $100.0\%$ | **100.00%** | PASS |

### Benchmark Query Suite
1. Query: `"generate and sign JSON Web Tokens with expiration"` → Target: `auth/jwt_handler.py:create_access_token` (Rank 1, 100% precision)
2. Query: `"validate and decode JWT cryptographic signature"` → Target: `auth/jwt_handler.py:verify_access_token` (Rank 1, 100% precision)
3. Query: `"PostgreSQL database connection context manager and transactions"` → Target: `database/connection.py:DatabaseManager` (Rank 1, 100% precision)
4. Query: `"system liveness probe and operational health check endpoint"` → Target: `api/router.py:health_check` (Rank 1, 100% precision)
5. Query: `"user login HTTP API endpoint"` → Target: `api/router.py:login_endpoint` (Rank 1, 100% precision)
6. Query: `"compute SHA-256 cryptographic hash digest of text"` → Target: `utils/crypto.py:calculate_sha256` (Rank 1, 100% precision)

---

## 4. Phase 6 Hybrid Retrieval Benchmark Results

Automated multi-strategy evaluation executed via `tests/evaluation/test_hybrid_evaluation.py`:

| Metric | Target Threshold | Measured Score | Status |
|---|---|---|---|
| **Intent Classification Accuracy** | $\ge 85.0\%$ | **100.00%** | PASS |
| **Hybrid Precision@1** | $\ge 70.0\%$ | **85.71%** | PASS |
| **Vector-Only Precision@1 (Baseline)** | Reference | **57.14%** | Baseline |
| **Keyword-Only Precision@1 (Baseline)**| Reference | **42.86%** | Baseline |
| **Hybrid Recall@3** | $\ge 85.0\%$ | **85.71%** | PASS |
| **Hybrid Mean Reciprocal Rank (MRR)** | $\ge 0.70$ | **0.857** | PASS |
| **Average End-to-End Latency** | $< 100\text{ ms}$ | **~8.3 ms** | PASS |

### Query Suite Breakdown by Category:

1. **Semantic Query**:
   - Query: `"cryptographic JWT signature validation and token decoding"`
   - Result: Rank 1 `auth/jwt.py:verify_token` (`[VECTOR + KEYWORD]`). Hit: **PASS**.
2. **Exact Symbol Query**:
   - Query: `"where is DatabaseClient.connect defined?"`
   - Result: Rank 1 `db/client.py:connect` (`[VECTOR + KEYWORD + GRAPH]`). Hit: **PASS**.
3. **Callers Query**:
   - Query: `"who calls verify_token in this project?"`
   - Result: Rank 1 `auth/service.py:authorize` (`[VECTOR + KEYWORD + GRAPH]`). Hit: **PASS**.
4. **Callees Query**:
   - Query: `"what does login invoke?"`
   - Result: Rank 1 `auth/jwt.py:create_token` (`[VECTOR + GRAPH]`). Hit: **PASS**.
5. **Dependencies Query**:
   - Query: `"what does auth/service.py depend on or import?"`
   - Result: Structural graph evidence captured imports of `create_token` & `verify_token`. Hit: **PASS**.
6. **Impact Analysis Query**:
   - Query: `"what could break if we modify auth/jwt.py?"`
   - Result: Rank 1 `auth/service.py:authorize` / `login` (`[VECTOR + GRAPH]`). Hit: **PASS**.
7. **Configuration Query**:
   - Query: `"where are environment settings DATABASE_URL and SECRET_KEY configured?"`
   - Result: Rank 1 `config.py` (`[VECTOR + KEYWORD]`). Hit: **PASS**.

---

## 5. Phase 7 Grounded Generation & Anti-Hallucination Benchmark Results

Automated grounding evaluation executed via `tests/evaluation/test_grounding_evaluation.py`:

| Metric | Target Threshold | Measured Score | Status |
|---|---|---|---|
| **Answerable Queries Grounded** | $\ge 90.0\%$ | **100.00%** (9/9) | PASS |
| **Unanswerable Case Honesty** | $100.0\%$ | **100.00%** (1/1) | PASS |
| **Citation Precision & Validity** | $100.0\%$ | **100.00%** (11/11) | PASS |
| **Unsupported Claim Rate (Hallucination)** | $0.0\%$ | **0.00%** | PASS |
| **Average Pipeline Latency** | $< 100\text{ ms}$ | **16.51 ms** | PASS |

### Grounding Query Suite Breakdown:

1. **Q1 (Password Hashing)**:
   - Query: `"Where is password hashing implemented and what algorithm is used?"`
   - Evidence: `src/auth/service.py:12-28` (`hash_password`, bcrypt).
   - Result: Grounded citation `[src/auth/service.py:12-28]`. Status: **PASS (Grounded)**.
2. **Q2 (Password Verification)**:
   - Query: `"How is user password verification performed?"`
   - Evidence: `src/auth/service.py:30-45` (`verify_password`, bcrypt `checkpw`).
   - Result: Grounded citation `[src/auth/service.py:30-45]`. Status: **PASS (Grounded)**.
3. **Q3 (Database Lifecycle)**:
   - Query: `"Which function initializes and manages the database session lifecycle?"`
   - Evidence: `src/database/session.py:10-25` (`get_db_session`).
   - Result: Grounded citation `[src/database/session.py:10-25]`. Status: **PASS (Grounded)**.
4. **Q4 (Login Endpoint)**:
   - Query: `"What endpoint handles developer or user login?"`
   - Evidence: `src/api/routes.py:15-40` (`login_route`).
   - Result: Grounded citation `[src/api/routes.py:15-40]`. Status: **PASS (Grounded)**.
5. **Q5 (User Entity Schema)**:
   - Query: `"What schema and fields are defined on the User entity model?"`
   - Evidence: `src/models/user.py:8-24` (`User` class).
   - Result: Grounded citation `[src/models/user.py:8-24]`. Status: **PASS (Grounded)**.
6. **Q6 (Cross-Layer Call Flow)**:
   - Query: `"Trace the structural call from the login route to authentication service."`
   - Evidence: `src/api/routes.py:15-40` and `src/auth/service.py:12-28`.
   - Result: Grounded citations to both files + confirmed graph relation. Status: **PASS (Grounded)**.
7. **Q7 (Application Configuration)**:
   - Query: `"What application configuration settings are declared?"`
   - Evidence: `src/core/config.py:5-22` (`AppSettings`).
   - Result: Grounded citation `[src/core/config.py:5-22]`. Status: **PASS (Grounded)**.
8. **Q8 (Caller Traversal)**:
   - Query: `"Who calls verify_password in the codebase?"`
   - Evidence: Knowledge graph edge `authenticate_user -> verify_password` at line 35.
   - Result: Grounded citation `[src/auth/service.py:30-45]`. Status: **PASS (Grounded)**.
9. **Q9 (Multi-Component Architecture)**:
   - Query: `"Explain how the login route relates to password hashing and database models."`
   - Evidence: `src/api/routes.py` and `src/auth/service.py`.
   - Result: Valid citations to both components. Status: **PASS (Grounded)**.
10. **Q10 (Anti-Hallucination Guardrail / Unindexed Concepts)**:
    - Query: `"How is the quantum error correction code and topological qubit surface initialized?"`
    - Evidence: `NO_EVIDENCE` (0 chunks, 0 graph edges).
    - Result: Explicit statement of insufficient codebase evidence; 0 citations; 0% unsupported claim rate. Status: **PASS (Honest-ZeroHallucination)**.

---

## 4. Phase 8: Advanced Repository Intelligence Benchmark

Evaluated on multi-file repositories with interconnected architecture layers (API, Service, Gateway, Database):

| Metric | Target | Measured Result | Status |
| :--- | :--- | :--- | :--- |
| **Backend Test Pass Rate** | 100.0% | **130 / 130 passing (100.0%)** | **PASS** |
| **Change Impact Precision** | $\ge 90.0\%$ | **100.0%** | **PASS** |
| **Change Impact Recall** | $\ge 90.0\%$ | **100.0%** | **PASS** |
| **Cycle Resistance (Infinite Loop Proof)** | 100.0% | **100.0% (Zero duplicates/hangs)** | **PASS** |
| **Risk Score Monotonicity** | 100.0% | **100.0% (Strictly non-decreasing)** | **PASS** |
| **Execution Flow Path Integrity** | 100.0% | **100.0% (Valid graph edges)** | **PASS** |
| **Citation Precision in Reports** | 100.0% | **100.0% verified line ranges** | **PASS** |
| **Frontend Production Build** | Clean | **0 errors, 416ms build time** | **PASS** |

### Benchmark Test Scenarios

1. **Impact Analysis Ground Truth**:
   - Evaluated target: `execute_transaction` called directly by `create_payment` and `refund_payment`.
   - Identified direct callers: `{"create_payment", "refund_payment"}` (Precision: 1.0, Recall: 1.0).
   - Classified downstream dependencies: `call_stripe_api`, `save_tx_record`.
   - Verified file blast radius: 3 distinct files.

2. **Risk Score Monotonicity**:
   - 1 dependent in 1 file: RiskScore = 25.0 (`LOW`).
   - 3 dependents across 3 files: RiskScore = 65.0 (`HIGH`).
   - 10 callers across 10 files with API endpoint: RiskScore = 100.0 (`CRITICAL`).
   - Monotonic property: $S(D_1) < S(D_2) < S(D_3)$, verified.

3. **Execution Flow Integrity**:
   - Traced sequence: `create_payment` -> `execute_transaction` -> `call_stripe_api` / `save_tx_record`.
   - All steps correctly identified as AST-valid successors with cross-file boundaries flagged.

4. **Citation Validity**:
   - 100% of generated inline citations in intelligence summaries resolved to verified source file paths and valid line coordinates.



