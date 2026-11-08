"""
Result Normalization, Deduplication and Hybrid Ranking via Reciprocal Rank Fusion (RRF).
Merges candidates retrieved from Vector RAG, GraphRAG, and Keyword Search into a unified,
calibrated, and deduplicated ranked list.
"""

from typing import List, Dict, Any, Optional
from collections import defaultdict

from backend.app.retrieval.retrieval_models import UnifiedSearchResult


class ResultFusion:
    """
    Implements Reciprocal Rank Fusion (RRF) and deduplication across multi-engine retrieval outputs.
    """

    def __init__(self, default_k: int = 60):
        self.default_k = default_k

    def fuse_and_rank(
        self,
        vector_results: List[UnifiedSearchResult],
        keyword_results: List[UnifiedSearchResult],
        graph_results: List[UnifiedSearchResult],
        top_k: int = 10,
        k: Optional[int] = None,
        weights: Optional[Dict[str, float]] = None,
    ) -> List[UnifiedSearchResult]:
        """
        Merges results using Reciprocal Rank Fusion:
            RRF(d) = sum_{s in sources} w_s * (1.0 / (k + rank_s(d)))

        Preserves all individual engine scores, tracks multi-source provenance,
        and deduplicates overlapping code regions.
        """
        rrf_k = k or self.default_k
        engine_weights = {
            "VECTOR": 1.0,
            "KEYWORD": 1.1,  # Slight boost to exact keyword / identifier matches
            "GRAPH": 0.95,
        }
        if weights:
            engine_weights.update(weights)

        # Map unique chunk key -> (accumulated_rrf_score, merged_result)
        scores: Dict[str, float] = defaultdict(float)
        candidates: Dict[str, UnifiedSearchResult] = {}

        def _get_key(item: UnifiedSearchResult) -> str:
            if item.chunk_id:
                return item.chunk_id
            return f"{item.file_path}:{item.start_line}-{item.end_line}"

        # 1. Process Vector results
        for rank, res in enumerate(vector_results, start=1):
            key = _get_key(res)
            w = engine_weights.get("VECTOR", 1.0)
            scores[key] += w * (1.0 / (rrf_k + rank))

            if key not in candidates:
                candidates[key] = res.model_copy(deep=True)
                candidates[key].sources = ["VECTOR"]
            else:
                if "VECTOR" not in candidates[key].sources:
                    candidates[key].sources.append("VECTOR")

        # 2. Process Keyword results
        for rank, res in enumerate(keyword_results, start=1):
            key = _get_key(res)
            w = engine_weights.get("KEYWORD", 1.0)
            scores[key] += w * (1.0 / (rrf_k + rank))

            if key not in candidates:
                candidates[key] = res.model_copy(deep=True)
                candidates[key].sources = ["KEYWORD"]
            else:
                if "KEYWORD" not in candidates[key].sources:
                    candidates[key].sources.append("KEYWORD")
                # Keep signature or docstring if keyword entry had it
                if not candidates[key].signature and res.signature:
                    candidates[key].signature = res.signature
                if not candidates[key].docstring and res.docstring:
                    candidates[key].docstring = res.docstring

        # 3. Process Graph results
        for rank, res in enumerate(graph_results, start=1):
            key = _get_key(res)
            w = engine_weights.get("GRAPH", 1.0)
            scores[key] += w * (1.0 / (rrf_k + rank))

            if key not in candidates:
                candidates[key] = res.model_copy(deep=True)
                candidates[key].sources = ["GRAPH"]
            else:
                if "GRAPH" not in candidates[key].sources:
                    candidates[key].sources.append("GRAPH")

        if not candidates:
            return []

        # Find max RRF score for calibration / normalization in [0.0, 1.0]
        max_rrf = max(scores.values()) if scores else 1.0

        # Build final unified ranked list
        ranked: List[UnifiedSearchResult] = []
        for key, candidate in candidates.items():
            rrf_score = scores[key]
            candidate.rrf_score = round(rrf_score, 6)

            # Combined retrieval source description
            if len(candidate.sources) > 1:
                candidate.retrieval_source = "HYBRID (" + " + ".join(candidate.sources) + ")"
            else:
                candidate.retrieval_source = candidate.sources[0]

            # Calibrate normalized score
            candidate.normalized_score = round(min(1.0, rrf_score / (max_rrf or 1.0)), 4)
            ranked.append(candidate)

        # Sort descending by RRF score
        ranked.sort(key=lambda x: x.rrf_score, reverse=True)

        return ranked[:top_k]


# Global singleton instance
result_fusion = ResultFusion()

