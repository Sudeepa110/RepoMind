"""
Unit tests for Phase 9 Retrieval Benchmark Runner.
Verifies multi-strategy comparison calculations, alias compatibility,
and summary aggregation across vector, keyword, graph, and hybrid strategies.
"""

from unittest.mock import MagicMock
import pytest

from backend.evaluation.retrieval_benchmark import RetrievalBenchmarkRunner
from backend.app.retrieval.retrieval_models import UnifiedSearchResult, RetrievalStrategy


@pytest.fixture
def mock_retriever():
    retriever = MagicMock()

    # Create dummy search results
    res1 = UnifiedSearchResult(
        chunk_id="c1",
        repository_id="test_repo",
        file_path="auth/jwt.py",
        start_line=10,
        end_line=25,
        source_code="def verify_token(): pass",
        retrieval_source="VECTOR",
        normalized_score=0.95,
        symbol_name="verify_token",
    )
    res2 = UnifiedSearchResult(
        chunk_id="c2",
        repository_id="test_repo",
        file_path="api/routes.py",
        start_line=30,
        end_line=45,
        source_code="def login(): pass",
        retrieval_source="KEYWORD",
        normalized_score=0.85,
        symbol_name="login",
    )
    res3 = UnifiedSearchResult(
        chunk_id="c3",
        repository_id="test_repo",
        file_path="db/models.py",
        start_line=1,
        end_line=15,
        source_code="class User: pass",
        retrieval_source="GRAPH",
        normalized_score=0.75,
        symbol_name="User",
    )

    dummy_response = MagicMock()
    dummy_response.results = [res1, res2, res3]
    dummy_response.assembled_context = "Context: def verify_token(): pass"
    dummy_response.latency_ms = 12.5

    retriever.hybrid_search.return_value = dummy_response
    return retriever


def test_evaluate_query_metrics(mock_retriever):
    runner = RetrievalBenchmarkRunner(retriever=mock_retriever)

    query_spec = {
        "id": "q1",
        "category": "EXACT_SYMBOL",
        "query": "verify jwt token",
        "expected_files": ["auth/jwt.py"],
        "expected_symbols": ["verify_token"],
        "ground_truth_lines": {"auth/jwt.py": [10, 25]},
    }

    result = runner.evaluate_query(
        repository_id="test_repo",
        query_record=query_spec,
        strategy="hybrid",
    )

    # Check that both @ and _at_ aliases are present and valid
    assert result["precision_at_1"] == 1.0
    assert result["precision@1"] == 1.0
    assert result["recall_at_3"] == 1.0
    assert result["recall@3"] == 1.0
    assert result["mrr"] == 1.0
    assert result["ndcg_at_5"] == 1.0
    assert result["file_accuracy"] == 1.0
    assert result["symbol_accuracy"] == 1.0
    assert result["strategy"] == "hybrid"


def test_summary_by_strategy_structure(mock_retriever):
    runner = RetrievalBenchmarkRunner(retriever=mock_retriever)

    queries = [
        {
            "id": "q1",
            "category": "SEMANTIC",
            "query": "jwt authentication",
            "expected_files": ["auth/jwt.py"],
            "expected_symbols": ["verify_token"],
        },
        {
            "id": "q2",
            "category": "EXACT_SYMBOL",
            "query": "login endpoint",
            "expected_files": ["api/routes.py"],
            "expected_symbols": ["login"],
        },
    ]

    result_obj = runner.run_benchmark(
        repository_id="test_repo",
        query_records=queries,
        strategies=["vector_only", "keyword_only", "hybrid"],
    )

    summary = result_obj["summary"]
    assert "vector_only" in summary
    assert "keyword_only" in summary
    assert "hybrid" in summary

    for strat_key, metrics in summary.items():
        assert "precision@1" in metrics
        assert "precision_at_1" in metrics
        assert "recall@3" in metrics
        assert "recall_at_3" in metrics
        assert "mrr" in metrics
        assert "ndcg@5" in metrics
        assert "latency_p50_ms" in metrics
