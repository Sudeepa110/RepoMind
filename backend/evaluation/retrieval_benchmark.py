"""
Multi-Strategy Retrieval Benchmarking Engine (Phase 9).
Evaluates Vector-only, Keyword-only, Graph-only, and Hybrid retrieval strategies
on standardized ground-truth benchmark datasets.
Measures Precision@k, Recall@k, MRR, nDCG@5, Symbol Accuracy, File Accuracy, and Latencies.
"""

import time
import logging
from typing import Dict, Any, List, Set, Optional

from backend.app.retrieval.hybrid_retriever import HybridRetriever, hybrid_retriever
from backend.app.retrieval.retrieval_models import HybridSearchRequest
from backend.evaluation.metrics import (
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    ndcg_at_k,
    calculate_percentile,
)

logger = logging.getLogger(__name__)


class RetrievalBenchmarkRunner:
    """
    Executes independent retrieval strategy benchmarks against ground-truth datasets.
    """

    def __init__(self, retriever: Optional[HybridRetriever] = None):
        self.retriever = retriever or hybrid_retriever

    def evaluate_query(
        self,
        repository_id: str,
        query_record: Dict[str, Any],
        strategy: str,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """
        Executes a single benchmark query using the designated strategy:
        - 'vector_only'
        - 'keyword_only'
        - 'graph_only'
        - 'hybrid'
        """
        query = query_record["query"]
        expected_files = set(f.replace("\\", "/").lower() for f in query_record.get("expected_files", []))
        expected_symbols = set(query_record.get("expected_symbols", []))
        should_abstain = query_record.get("should_abstain", False)

        include_vector = strategy in ("vector_only", "hybrid")
        include_keyword = strategy in ("keyword_only", "hybrid")
        include_graph = strategy in ("graph_only", "hybrid")

        req = HybridSearchRequest(
            query=query,
            top_k=top_k,
            include_vector=include_vector,
            include_keyword=include_keyword,
            include_graph=include_graph,
        )

        t0 = time.perf_counter()
        res = self.retriever.hybrid_search(repository_id, req)
        latency_ms = (time.perf_counter() - t0) * 1000

        retrieved_files = [c.file_path.replace("\\", "/").lower() for c in res.results]
        retrieved_symbols = [c.symbol_name for c in res.results if c.symbol_name]

        # Combine file paths and symbol names for unified target relevance check
        ground_truth_targets = expected_files.union(expected_symbols)
        retrieved_targets = []
        for c in res.results:
            c_file = c.file_path.replace("\\", "/").lower()
            if c.symbol_name:
                retrieved_targets.append(c.symbol_name)
            retrieved_targets.append(c_file)

        # Unique target representation maintaining rank order
        ordered_targets = []
        for t in retrieved_targets:
            if t not in ordered_targets:
                ordered_targets.append(t)

        if should_abstain:
            # If query is out of scope/unanswerable, 0 results or low confidence is correct
            p1 = 1.0 if not res.results else 0.0
            p3 = 1.0 if not res.results else 0.0
            p5 = 1.0 if not res.results else 0.0
            r3 = 1.0
            r5 = 1.0
            mrr = 1.0 if not res.results else 0.0
            ndcg5 = 1.0 if not res.results else 0.0
            file_acc = 1.0 if not res.results else 0.0
            sym_acc = 1.0 if not res.results else 0.0
        else:
            p1 = precision_at_k(ordered_targets, ground_truth_targets, 1)
            p3 = precision_at_k(ordered_targets, ground_truth_targets, 3)
            p5 = precision_at_k(ordered_targets, ground_truth_targets, 5)
            r3 = recall_at_k(ordered_targets, ground_truth_targets, 3)
            r5 = recall_at_k(ordered_targets, ground_truth_targets, 5)
            mrr = reciprocal_rank(ordered_targets, ground_truth_targets)
            ndcg5 = ndcg_at_k(ordered_targets, ground_truth_targets, 5)

            # Accuracy flags
            file_acc = 1.0 if any(f in expected_files for f in retrieved_files[:3]) else 0.0
            sym_acc = 1.0 if any(s in expected_symbols for s in retrieved_symbols[:3]) or not expected_symbols else 0.0

        return {
            "query_id": query_record.get("query_id"),
            "query": query,
            "strategy": strategy,
            "latency_ms": latency_ms,
            "precision_at_1": p1,
            "precision_at_3": p3,
            "precision_at_5": p5,
            "recall_at_3": r3,
            "recall_at_5": r5,
            "mrr": mrr,
            "ndcg_at_5": ndcg5,
            "precision@1": p1,
            "precision@3": p3,
            "precision@5": p5,
            "recall@3": r3,
            "recall@5": r5,
            "ndcg@5": ndcg5,
            "file_accuracy": file_acc,
            "symbol_accuracy": sym_acc,
            "results_count": len(res.results),
        }

    def run_benchmark(
        self,
        repository_id: str,
        query_records: List[Dict[str, Any]],
        strategies: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """
        Runs full multi-strategy benchmark suite and aggregates metrics.
        """
        eval_strategies = strategies or ["vector_only", "keyword_only", "graph_only", "hybrid"]
        results_by_strategy: Dict[str, List[Dict[str, Any]]] = {s: [] for s in eval_strategies}
        summary_by_strategy: Dict[str, Dict[str, float]] = {}

        for strat in eval_strategies:
            latencies = []
            p1_list = []
            p3_list = []
            p5_list = []
            r3_list = []
            r5_list = []
            mrr_list = []
            ndcg5_list = []
            file_acc_list = []
            sym_acc_list = []

            for q_rec in query_records:
                eval_item = self.evaluate_query(repository_id, q_rec, strategy=strat, top_k=top_k)
                results_by_strategy[strat].append(eval_item)

                latencies.append(eval_item["latency_ms"])
                p1_list.append(eval_item["precision_at_1"])
                p3_list.append(eval_item["precision_at_3"])
                p5_list.append(eval_item["precision_at_5"])
                r3_list.append(eval_item["recall_at_3"])
                r5_list.append(eval_item["recall_at_5"])
                mrr_list.append(eval_item["mrr"])
                ndcg5_list.append(eval_item["ndcg_at_5"])
                file_acc_list.append(eval_item["file_accuracy"])
                sym_acc_list.append(eval_item["symbol_accuracy"])

            n = max(1, len(query_records))
            summary_by_strategy[strat] = {
                "precision_at_1": round(sum(p1_list) / n, 4),
                "precision_at_3": round(sum(p3_list) / n, 4),
                "precision_at_5": round(sum(p5_list) / n, 4),
                "recall_at_3": round(sum(r3_list) / n, 4),
                "recall_at_5": round(sum(r5_list) / n, 4),
                "mrr": round(sum(mrr_list) / n, 4),
                "ndcg_at_5": round(sum(ndcg5_list) / n, 4),
                "precision@1": round(sum(p1_list) / n, 4),
                "precision@3": round(sum(p3_list) / n, 4),
                "precision@5": round(sum(p5_list) / n, 4),
                "recall@3": round(sum(r3_list) / n, 4),
                "recall@5": round(sum(r5_list) / n, 4),
                "ndcg@5": round(sum(ndcg5_list) / n, 4),
                "file_accuracy": round(sum(file_acc_list) / n, 4),
                "symbol_accuracy": round(sum(sym_acc_list) / n, 4),
                "mean_latency_ms": round(sum(latencies) / n, 2),
                "latency_p50_ms": round(calculate_percentile(latencies, 50), 2),
                "p50_latency_ms": round(calculate_percentile(latencies, 50), 2),
                "latency_p95_ms": round(calculate_percentile(latencies, 95), 2),
                "p95_latency_ms": round(calculate_percentile(latencies, 95), 2),
                "p99_latency_ms": round(calculate_percentile(latencies, 99), 2),
                "total_queries": len(query_records),
            }

        return {
            "repository_id": repository_id,
            "total_queries": len(query_records),
            "strategies_evaluated": eval_strategies,
            "summary": summary_by_strategy,
            "detailed_results": results_by_strategy,
        }


retrieval_benchmark_runner = RetrievalBenchmarkRunner()
