"""
Unit tests for Phase 9 Evaluation Framework - Information Retrieval & Statistical Metrics.
Verifies mathematical correctness of Precision@k, Recall@k, Reciprocal Rank, nDCG@k,
percentile calculation, and line citation overlap.
"""

import math
import pytest
from backend.evaluation.metrics import (
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    ndcg_at_k,
    calculate_percentile,
    line_overlap_iou,
)


def test_precision_at_k():
    retrieved = ["auth.py", "jwt.py", "main.py", "db.py"]
    relevant = {"auth.py", "jwt.py", "config.py"}

    # P@1: top 1 is "auth.py" which is relevant -> 1.0
    assert precision_at_k(retrieved, relevant, k=1) == 1.0

    # P@2: top 2 are both relevant -> 2/2 = 1.0
    assert precision_at_k(retrieved, relevant, k=2) == 1.0

    # P@3: top 3 has 2 relevant -> 2/3 = 0.6667
    assert pytest.approx(precision_at_k(retrieved, relevant, k=3), 0.001) == 2 / 3

    # P@4: top 4 has 2 relevant -> 2/4 = 0.5
    assert precision_at_k(retrieved, relevant, k=4) == 0.5

    # Empty inputs
    assert precision_at_k([], relevant, k=1) == 0.0
    assert precision_at_k(retrieved, set(), k=1) == 0.0
    assert precision_at_k(retrieved, relevant, k=0) == 0.0


def test_recall_at_k():
    retrieved = ["auth.py", "db.py", "jwt.py", "main.py"]
    relevant = {"auth.py", "jwt.py", "config.py"}  # 3 relevant items total

    # R@1: top 1 has 1 relevant out of 3 -> 1/3
    assert pytest.approx(recall_at_k(retrieved, relevant, k=1), 0.001) == 1 / 3

    # R@2: top 2 has 1 relevant ("auth.py") -> 1/3
    assert pytest.approx(recall_at_k(retrieved, relevant, k=2), 0.001) == 1 / 3

    # R@3: top 3 has 2 relevant ("auth.py", "jwt.py") -> 2/3
    assert pytest.approx(recall_at_k(retrieved, relevant, k=3), 0.001) == 2 / 3

    # Empty relevant set
    assert recall_at_k(retrieved, set(), k=3) == 1.0
    assert recall_at_k([], relevant, k=3) == 0.0


def test_reciprocal_rank():
    relevant = {"db.py"}

    # First position
    assert reciprocal_rank(["db.py", "auth.py"], relevant) == 1.0

    # Second position
    assert reciprocal_rank(["auth.py", "db.py"], relevant) == 0.5

    # Third position
    assert pytest.approx(reciprocal_rank(["auth.py", "main.py", "db.py"], relevant), 0.001) == 1 / 3

    # Not found
    assert reciprocal_rank(["auth.py", "main.py"], relevant) == 0.0

    # Empty
    assert reciprocal_rank([], relevant) == 0.0
    assert reciprocal_rank(["db.py"], set()) == 0.0


def test_ndcg_at_k():
    relevant = {"a", "b"}

    # Perfect ranking: both relevant items at rank 1 and 2
    perfect = ["a", "b", "c", "d"]
    assert pytest.approx(ndcg_at_k(perfect, relevant, k=2), 0.001) == 1.0
    assert pytest.approx(ndcg_at_k(perfect, relevant, k=5), 0.001) == 1.0

    # Inverted ranking: non-relevant at rank 1, relevant at rank 2 and 3
    imperfect = ["c", "a", "b", "d"]
    score = ndcg_at_k(imperfect, relevant, k=3)
    assert 0.0 < score < 1.0

    # No relevant items retrieved
    unrelated = ["x", "y", "z"]
    assert ndcg_at_k(unrelated, relevant, k=3) == 0.0

    # Edge cases
    assert ndcg_at_k([], relevant, k=3) == 0.0
    assert ndcg_at_k(perfect, set(), k=3) == 0.0
    assert ndcg_at_k(perfect, relevant, k=0) == 0.0


def test_calculate_percentile():
    values = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]

    # p50 (median)
    assert pytest.approx(calculate_percentile(values, 50), 0.1) == 55.0

    # p0 and p100
    assert calculate_percentile(values, 0) == 10.0
    assert calculate_percentile(values, 100) == 100.0

    # Empty values
    assert calculate_percentile([], 50) == 0.0

    # Single value
    assert calculate_percentile([42.5], 95) == 42.5


def test_line_overlap_iou():
    # Exact match: [10, 20] and [10, 20] -> IoU = 1.0
    assert line_overlap_iou(10, 20, 10, 20) == 1.0

    # Partial overlap: [10, 20] (11 lines) and [15, 25] (11 lines)
    # Intersection: [15, 20] (6 lines: 15,16,17,18,19,20)
    # Union: [10, 25] (16 lines) -> IoU = 6 / 16 = 0.375
    assert pytest.approx(line_overlap_iou(10, 20, 15, 25), 0.001) == 6 / 16

    # Disjoint ranges: [10, 20] and [30, 40] -> IoU = 0.0
    assert line_overlap_iou(10, 20, 30, 40) == 0.0

    # Inverted range normalization: [20, 10] normalized to [10, 20]
    assert line_overlap_iou(20, 10, 10, 20) == 1.0
