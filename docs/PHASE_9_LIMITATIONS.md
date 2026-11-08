# RepoMind — Phase 9.3 Limitations, Boundaries & Evaluation Transparency

## 1. Overview

Phase 9.3 establishes query-adaptive retrieval routing, balanced honest abstention evaluation, and claim-level answer grounding. To maintain strict scientific transparency, this document details known limitations, architectural boundaries, and specific root causes of benchmark defect patterns.

---

## 2. Abstention False-Answer Root Causes & Boundaries

The balanced 40-query abstention benchmark reported an **overall accuracy of 82.50%**, with **100.0% abstention precision** and **70.83% abstention recall**. Across 24 out-of-scope queries, 7 failed to trigger honest abstention (false-answer rate: 29.17%). 

Technical analysis reveals three specific causes:

### 2.1 Common Route Path Segment Token Collisions
- **Affected Category**: Nonexistent API Endpoints (`ABSTAIN_07`, `ABSTAIN_08`, `ABSTAIN_09`).
- **Mechanism**: Queries such as `"How is the DELETE /api/v2/users/crypto_wallet endpoint implemented?"` contain path tokens `/api/` and `/users/`. In `routes.py`, existing endpoints (`POST /api/v1/auth/login`) also match the tokens `api` and `users`.
- **Consequence**: SQLite FTS5 matches the shared path prefixes, and ChromaDB embeddings find lexical similarity to HTTP route declarations, passing the sufficiency threshold.
- **Future Direction**: Requires dedicated endpoint URL route-trie matching rather than sub-token bag-of-words parsing.

### 2.2 Semantic Substring Overlap in Unavailable Evidence Queries
- **Affected Category**: Unavailable Credentials & Plausible Identifiers (`ABSTAIN_20`, `ABSTAIN_23`).
- **Mechanism**: A query asking for `"What is the live AWS production database master password in this repository?"` contains the words `database` and `password`. Both `database/session.py` and `utils/hash.py` (which contain `hash_password`) match these terms with high confidence.
- **Consequence**: The system locates code relating to passwords and database sessions and treats the query as answerable rather than recognizing that live production credentials are out of scope.

### 2.3 Partial Class Match on Nonexistent Methods
- **Affected Category**: Plausible Nonexistent Identifiers (`ABSTAIN_23`: `UserRepository.findUsersWithExpiredCreditCards`).
- **Mechanism**: While `findUsersWithExpiredCreditCards` does not exist, `UserRepository` does exist. Keyword search locates `UserRepository`, returning the class chunk.
- **Consequence**: The system classifies the evidence as sufficient for the class entity, despite the requested method being absent.

---

## 3. Retrieval Strategy Boundaries & Non-Universal Superiority

RepoMind does not claim that Hybrid Retrieval is universally superior in all metrics or scenarios:

1. **Graph-Only Advantages**: On repositories with dense AST call graphs (e.g., `synthetic_java_petclinic_repo` and `synthetic_ts_express_repo`), Graph-only retrieval achieves higher Precision@1 (**0.7778**) and MRR (**0.7778**) than Hybrid (0.5556 and 0.6204) because Graph search eliminates all lexical and semantic noise.
2. **Keyword-Only Latency Advantage**: SQLite FTS5 executes in **1.14 – 2.32 ms** (5–10x faster than dense vector embedding). When developers search for exact function names, keyword search provides immediate answers with zero embedding compute overhead.
3. **Vector-Only Recall Advantage**: On `real_world_ky_subset` and `real_world_flask_subset`, Vector-only retrieval achieves equivalent or higher Recall@5 (0.9000 and 0.8167) and MRR (0.6818 vs 0.6364) compared to Hybrid, because RRF rank fusion occasionally deprioritizes top vector hits when keyword tokens mismatch.
4. **Hybrid Latency Cost**: Hybrid retrieval incurs the highest latency (**4.29 – 8.93 ms**) because it executes multiple retrieval pipelines and rank fusion.

---

## 4. Evaluation Scope & Methodology Boundaries

### 4.1 Deterministic Citation Math vs Stochastic LLM Generation
- **Scope**: Offline benchmark citation validity (100%) measures the deterministic regex parser, AST chunk coordinate math, and line interval overlap IoU.
- **Boundary**: It verifies that when citations are constructed from retrieved code, they are coordinate-accurate. It does not replace live evaluation against non-deterministic LLMs that may hallucinate file names or line numbers.

### 4.2 Development Set vs Held-Out Query Subset
- **Methodology**: To prevent overfitting, 16 benchmark queries (`Q39`–`Q54`) and all 40 abstention queries were authored as an independent held-out evaluation set, evaluated without post-hoc hyperparameter tuning.

### 4.3 Static AST Parsing vs Runtime Dynamic Behavior
- **Boundary**: Tree-sitter AST parsing operates strictly on static source text. Dynamic Python dispatch tables (`getattr()`), TypeScript ambient declarations (`declare module`), and Java runtime reflection (`Class.forName()`) remain unresolved at the static graph level.
