"""
Unit tests for Reciprocal Rank Fusion (RRF) and Result Fusion (Phase 6).
Verifies rank reciprocal formula, multi-source provenance tracking,
score calibration in [0.0, 1.0], and deduplication.
"""

import pytest
from backend.app.retrieval.retrieval_models import UnifiedSearchResult
from backend.app.retrieval.result_fusion import ResultFusion


@pytest.fixture
def fusion():
    return ResultFusion(default_k=60)


def create_search_result(chunk_id: str, file_path: str, symbol_name: str, score: float, source: str):
    return UnifiedSearchResult(
        chunk_id=chunk_id,
        repository_id="test_repo",
        file_path=file_path,
        symbol_name=symbol_name,
        symbol_type="FUNCTION",
        language="python",
        start_line=1,
        end_line=10,
        source_code=f"def {symbol_name}(): pass",
        retrieval_source=source,
        sources=[source],
        original_score=score,
        normalized_score=score,
        rrf_score=0.0,
    )


def test_rrf_single_source(fusion):
    vector_results = [
        create_search_result("c1", "a.py", "func_a", 0.9, "VECTOR"),
        create_search_result("c2", "b.py", "func_b", 0.8, "VECTOR"),
    ]

    ranked = fusion.fuse_and_rank(vector_results=vector_results, keyword_results=[], graph_results=[], top_k=5)

    assert len(ranked) == 2
    assert ranked[0].chunk_id == "c1"
    assert ranked[1].chunk_id == "c2"
    # Rank 1 RRF: 1.0 / (60 + 1) = 0.016393
    assert pytest.approx(ranked[0].rrf_score, rel=1e-3) == 0.016393
    assert ranked[0].normalized_score == 1.0  # Max score normalized to 1.0
    assert ranked[0].sources == ["VECTOR"]


def test_rrf_multi_source_deduplication(fusion):
    # c1 is rank 1 in VECTOR and rank 1 in KEYWORD
    # c2 is rank 2 in VECTOR only
    # c3 is rank 2 in KEYWORD only
    vector_results = [
        create_search_result("c1", "auth.py", "verify_pwd", 0.95, "VECTOR"),
        create_search_result("c2", "auth.py", "hash_pwd", 0.70, "VECTOR"),
    ]
    keyword_results = [
        create_search_result("c1", "auth.py", "verify_pwd", -0.5, "KEYWORD"),
        create_search_result("c3", "db.py", "connect", -1.2, "KEYWORD"),
    ]

    ranked = fusion.fuse_and_rank(
        vector_results=vector_results,
        keyword_results=keyword_results,
        graph_results=[],
        top_k=5,
        k=60,
    )

    assert len(ranked) == 3
    # c1 must be rank 1 because it accumulated scores from both engines
    assert ranked[0].chunk_id == "c1"
    assert "VECTOR" in ranked[0].sources
    assert "KEYWORD" in ranked[0].sources
    assert "HYBRID" in ranked[0].retrieval_source

    # c1 RRF score should be approx: 1.0/(60+1) + 1.1/(60+1) = 2.1 / 61 = 0.034426
    expected_c1_rrf = (1.0 / 61.0) + (1.1 / 61.0)
    assert pytest.approx(ranked[0].rrf_score, rel=1e-3) == round(expected_c1_rrf, 6)


def test_rrf_top_k_limiting(fusion):
    vector_results = [
        create_search_result(f"c_{i}", f"f_{i}.py", f"func_{i}", 0.9 - i * 0.05, "VECTOR")
        for i in range(10)
    ]

    ranked = fusion.fuse_and_rank(
        vector_results=vector_results,
        keyword_results=[],
        graph_results=[],
        top_k=3,
    )

    assert len(ranked) == 3
    assert [r.chunk_id for r in ranked] == ["c_0", "c_1", "c_2"]
