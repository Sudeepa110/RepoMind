# Evaluation Framework

## Purpose

To prevent hallucinations and verify retrieval accuracy, RepoMind incorporates an automated and empirical evaluation framework.

## Evaluation Metrics

1. **Retrieval Precision@K**: Fraction of retrieved chunks that contain the actual ground-truth implementation for a user query.
2. **Context Recall**: Whether all essential functions/classes needed to answer the question are present in the top-K retrieved context.
3. **Citation Accuracy**: Percentage of cited file paths and line ranges that correspond to real, verifiable code symbols in the repository.
4. **Hallucination Rate**: Frequency of non-existent methods, arguments, or file paths generated in responses (Target: 0%).
5. **Latency & Throughput**: Time-to-first-token (TTFT) and total indexing time per 100 source files.

## Benchmark Dataset (Phase 1 Baseline)

| Repository | Test Case | Target Symbol | Status |
|---|---|---|---|
| `fastapi/fastapi` | Where is the FastAPI class defined? | `fastapi/applications.py:FastAPI` | Verified URL validation |
| `pallets/flask` | Where is the Flask app initialized? | `src/flask/app.py:Flask` | Verified URL validation |
| `pmndrs/zustand` | Where is createStore declared? | `src/vanilla.ts:createStore` | Verified URL validation |

Empirical retrieval and answer verification will be benchmarked as the RAG pipeline is built in Phases 4 through 6.
