# RepoMind — Phase 9.4 Limitations, Boundaries & Evaluation Transparency

## 1. Overview

Phase 9.4 completes exact API endpoint validation, multi-factor evidence sufficiency calibration, and expanded 72-query balanced abstention benchmarking. To maintain strict scientific transparency, this document details resolved defect mechanisms, remaining architectural boundaries, and known operational limits.

---

## 2. Phase 9.3 Defects Resolved in Phase 9.4

In Phase 9.3, the balanced abstention benchmark identified 7 false answers across 24 out-of-scope queries (false-answer rate: 29.17%). Phase 9.4 resolved these defects through structural matching mechanisms:

### 2.1 Resolution of Common Route Token Collisions
- **Prior Defect**: Nonexistent endpoints (`DELETE /api/v2/users/crypto_wallet`) passed sufficiency checks because substring tokens (`api`, `users`, `delete`) matched `routes.py`.
- **Phase 9.4 Resolution**: `EndpointMatcher` (`backend/app/retrieval/endpoint_matcher.py`) performs structurally justified route and HTTP method extraction. It normalizes path segments (supporting wildcards like `:id`, `<int:id>`, `{id}` -> `{param}`), parses declared routes across Flask, Express, and Spring Boot, and classifies route inquiries into:
  - `EXACT_MATCH`: Path segments and HTTP method match codebase declaration.
  - `METHOD_MISMATCH`: Route path exists, but queried method differs (e.g., `DELETE /api/v1/auth/login`).
  - `PREFIX_ONLY`: Only a common ancestor matches while leaf segments are absent (e.g., `/api/v2/users/crypto_wallet` vs `/users/`).
  - `NOT_FOUND`: Route path does not exist in code.
- **Empirical Result**: Nonexistent endpoints achieved **100% abstention recall** (13/13 true abstentions, 0 false answers).

### 2.2 Resolution of Unavailable Evidence & External Technology Collisions
- **Prior Defect**: Queries asking for live AWS master passwords or Cassandra clusters matched generic tokens (`database`, `password`, `service`).
- **Phase 9.4 Resolution**: Added distinctive subject validation (`DISTINCTIVE_SUBJECT_TERMS`). When a query specifies external cloud infrastructure, unsupported databases, or out-of-scope concepts (AWS, Azure, GCP, Cassandra, DynamoDB, ClickHouse, Stripe, GPU, PyPI secrets), the engine verifies the presence of these distinctive subjects in retrieved code chunks. If absent, the engine immediately yields `NO_EVIDENCE`.

### 2.3 Resolution of Qualified Member Mismatch
- **Prior Defect**: Queries for `UserRepository.findUsersWithExpiredCreditCards` matched `UserRepository`, returning class chunks as sufficient evidence.
- **Phase 9.4 Resolution**: Qualified identifiers (`Class.member`, `Class::member`) explicitly verify that the member name exists in the retrieved chunk's AST definitions or source code. If absent, `NO_EVIDENCE` is enforced.

---

## 3. Remaining Boundaries & Operational Limits (Phase 9.4)

### 3.1 Endpoint Resolution Depth & Dynamic Route Construction
1. **Static Declaration Matching**: `EndpointMatcher` extracts routes declared via standard framework constructs (`@app.route`, `@bp.route`, `router.get/post/delete`, `app.use`, `@GetMapping`, `@PostMapping`, `@RequestMapping`).
2. **Dynamic Route Construction Limit**: Dynamic route paths computed at runtime via variable concatenation or configuration lookups (e.g. `app.add_url_rule(get_custom_prefix() + "/data")`) are not resolved statically unless documented via route docstrings (`# Route: GET /path`).
3. **Cross-File Route Mounting**: When an Express sub-router is defined in `routes/api.ts` and mounted in `server.ts` via `app.use('/api/v1', router)`, full route composition occurs when both chunks are in retrieved context. If only the sub-router chunk is retrieved, the relative route is verified; if the query requests the mounted prefix, literal string matching or docstring annotations provide the composition bridge.

### 3.2 Retrieval Strategy Boundaries & Non-Universal Superiority
RepoMind explicitly documents that no single retrieval engine is universally superior across all evaluation metrics:
1. **Graph-Only Advantages**: On repositories with dense AST call graphs (e.g., `synthetic_java_petclinic_repo` and `synthetic_ts_express_repo`), Graph-only retrieval achieves higher Precision@1 (**0.7778**) and MRR (**0.7778**) than Hybrid (0.5556 and 0.6204) because Graph search eliminates all lexical and semantic noise.
2. **Keyword-Only Latency Advantage**: SQLite FTS5 executes in **1.14 – 2.32 ms** (5–10x faster than dense vector embedding). When developers search for exact function names, keyword search provides immediate answers with zero embedding compute overhead.
3. **Vector-Only Recall Advantage**: On `real_world_ky_subset` and `real_world_flask_subset`, Vector-only retrieval achieves equivalent or higher Recall@5 (0.9000 and 0.8167) and MRR (0.6818 vs 0.6364) compared to Hybrid, because RRF rank fusion occasionally deprioritizes top vector hits when keyword tokens mismatch.
4. **Hybrid Latency Cost**: Hybrid retrieval incurs the highest latency (**4.29 – 8.93 ms**) because it executes multiple retrieval pipelines and rank fusion.

### 3.3 Static AST Parsing vs Runtime Dynamic Behavior
- **Boundary**: Tree-sitter AST parsing operates strictly on static source text. Dynamic Python dispatch tables (`getattr()`), TypeScript ambient declarations (`declare module`), and Java runtime reflection (`Class.forName()`) remain unresolved at the static graph level.

### 3.4 Deterministic Evidence Sufficiency vs Stochastic LLM Hallucination
- **Boundary**: `evaluate_evidence_sufficiency()` provides deterministic gating preventing LLM generation when evidence is absent or insufficient. However, once sufficient evidence is confirmed, generative synthesis by Google Gemini remains subject to prompt adherence and LLM stochasticity, governed by citation validation and post-generation grounding verification.
