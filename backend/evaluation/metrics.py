"""
Formal Quantitative Information Retrieval & Ranking Metrics (Phase 9).
Implements Precision@k, Recall@k, MRR, nDCG@k, Line Overlap (IoU), and Latency Percentiles.
"""

import math
from typing import List, Set, Any, Tuple, Optional


def precision_at_k(retrieved: List[str], ground_truth: Set[str], k: int) -> float:
    """
    Computes Precision@k: fraction of top-k retrieved items that are relevant.
    """
    if k <= 0 or not retrieved:
        return 0.0
    top_k = retrieved[:k]
    hits = sum(1 for item in top_k if item in ground_truth)
    return hits / k


def recall_at_k(retrieved: List[str], ground_truth: Set[str], k: int) -> float:
    """
    Computes Recall@k: fraction of all relevant items retrieved in top-k.
    """
    if not ground_truth:
        return 1.0  # If nothing relevant, abstention was appropriate
    if k <= 0 or not retrieved:
        return 0.0
    top_k = retrieved[:k]
    hits = sum(1 for item in top_k if item in ground_truth)
    return hits / len(ground_truth)


def reciprocal_rank(retrieved: List[str], ground_truth: Set[str]) -> float:
    """
    Computes Reciprocal Rank (RR): 1 / rank of the first relevant item.
    """
    for idx, item in enumerate(retrieved, start=1):
        if item in ground_truth:
            return 1.0 / idx
    return 0.0


def dcg_at_k(relevance_scores: List[float], k: int) -> float:
    """
    Computes Discounted Cumulative Gain at rank k.
    """
    dcg = 0.0
    for idx, rel in enumerate(relevance_scores[:k], start=1):
        dcg += (2.0 ** rel - 1.0) / math.log2(idx + 1.0)
    return dcg


def ndcg_at_k(retrieved: List[str], ground_truth: Set[str], k: int) -> float:
    """
    Computes Normalized Discounted Cumulative Gain at rank k (nDCG@k).
    Binary relevance: 1 if item in ground_truth, else 0.
    """
    if not ground_truth or k <= 0 or not retrieved:
        return 0.0

    actual_rel = [1.0 if item in ground_truth else 0.0 for item in retrieved[:k]]
    actual_dcg = dcg_at_k(actual_rel, k)

    # Ideal DCG: all available relevant items ranked at the very top
    ideal_rel = [1.0] * min(k, len(ground_truth)) + [0.0] * max(0, k - len(ground_truth))
    ideal_dcg = dcg_at_k(ideal_rel, k)

    if ideal_dcg == 0.0:
        return 0.0
    return actual_dcg / ideal_dcg


def line_overlap_iou(
    pred_start: int, pred_end: int, true_start: int, true_end: int
) -> float:
    """
    Calculates Intersection-over-Union (IoU) of predicted vs true source line ranges.
    Automatically normalizes start/end bounds to handle inverted line inputs.
    """
    p_start, p_end = min(pred_start, pred_end), max(pred_start, pred_end)
    t_start, t_end = min(true_start, true_end), max(true_start, true_end)
    inter_start = max(p_start, t_start)
    inter_end = min(p_end, t_end)
    if inter_end < inter_start:
        return 0.0
    intersection = (inter_end - inter_start) + 1
    union = (max(p_end, t_end) - min(p_start, t_start)) + 1
    return intersection / max(1, union)


def calculate_percentile(values: List[float], p: float) -> float:
    """Computes the p-th percentile (0 to 100) of a list of numeric values."""
    if not values:
        return 0.0
    sorted_v = sorted(values)
    k = (len(sorted_v) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_v[int(k)]
    d0 = sorted_v[int(f)] * (c - k)
    d1 = sorted_v[int(c)] * (k - f)
    return d0 + d1
