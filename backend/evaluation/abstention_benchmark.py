"""
Balanced Abstention & Out-of-Scope Benchmark (Phase 9.3).
Evaluates honest abstention reliability, evidence sufficiency classification,
and anti-hallucination boundaries on balanced labeled datasets across 6 repositories.
Measures:
- Abstention precision & recall
- False-answer rate on out-of-scope queries
- False-abstention rate on answerable queries
- Overall accuracy
- 4-level evidence sufficiency distribution (NO_EVIDENCE, INSUFFICIENT, PARTIAL, SUFFICIENT)
- Category-level breakdown across all 8 out-of-scope categories and answerable controls.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

from backend.app.retrieval.hybrid_retriever import hybrid_retriever, HybridRetriever
from backend.app.retrieval.retrieval_models import HybridSearchRequest
from backend.app.llm.generation_service import generation_service, GenerationService
from backend.app.llm.generation_models import EvidenceSufficiency
from backend.evaluation.citation_evaluator import citation_evaluator, CitationAndGroundingEvaluator

logger = logging.getLogger(__name__)

ABSTENTION_QUERIES_FILE = Path(__file__).parent / "datasets" / "abstention_benchmark_queries.json"


class AbstentionBenchmarkRunner:
    """
    Executes balanced honest abstention evaluation across multi-language repositories.
    """

    def __init__(
        self,
        retriever: Optional[HybridRetriever] = None,
        gen_service: Optional[GenerationService] = None,
        evaluator: Optional[CitationAndGroundingEvaluator] = None,
    ):
        self.retriever = retriever or hybrid_retriever
        self.gen_service = gen_service or generation_service
        self.evaluator = evaluator or citation_evaluator

    def load_queries(self) -> List[Dict[str, Any]]:
        with open(ABSTENTION_QUERIES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def run_benchmark(self, queries: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Executes the full balanced abstention benchmark.
        """
        if queries is None:
            queries = self.load_queries()

        total_queries = len(queries)
        out_of_scope_queries = [q for q in queries if q["should_abstain"]]
        answerable_queries = [q for q in queries if not q["should_abstain"]]

        true_abstentions = 0      # Correctly abstained on out-of-scope
        false_answers = 0         # Failed to abstain on out-of-scope (hallucination risk)
        true_answers = 0          # Correctly answered answerable query
        false_abstentions = 0     # Incorrectly abstained on answerable query

        sufficiency_counts = {
            EvidenceSufficiency.NO_EVIDENCE.value: 0,
            EvidenceSufficiency.INSUFFICIENT.value: 0,
            EvidenceSufficiency.PARTIAL.value: 0,
            EvidenceSufficiency.SUFFICIENT.value: 0,
        }

        category_results: Dict[str, Dict[str, int]] = {}
        detailed_records: List[Dict[str, Any]] = []

        for q in queries:
            qid = q["query_id"]
            repo_id = q["repo_name"]
            query_text = q["query"]
            should_abstain = q["should_abstain"]
            category = q.get("category", "unknown")

            if category not in category_results:
                category_results[category] = {"total": 0, "correct": 0, "abstained": 0}
            category_results[category]["total"] += 1

            # Execute hybrid retrieval
            retrieval_res = self.retriever.hybrid_search(
                repository_id=repo_id,
                request=HybridSearchRequest(query=query_text, top_k=5),
            )

            # Classify evidence sufficiency
            sufficiency = self.gen_service.evaluate_evidence_sufficiency(retrieval_res)
            sufficiency_counts[sufficiency.value] += 1

            # Determine whether the system decides to abstain
            did_abstain = sufficiency in (EvidenceSufficiency.NO_EVIDENCE, EvidenceSufficiency.INSUFFICIENT)

            if did_abstain:
                category_results[category]["abstained"] += 1

            # Evaluate correctness
            if should_abstain:
                if did_abstain:
                    true_abstentions += 1
                    is_correct = True
                else:
                    false_answers += 1
                    is_correct = False
            else:
                if not did_abstain:
                    true_answers += 1
                    is_correct = True
                else:
                    false_abstentions += 1
                    is_correct = False

            if is_correct:
                category_results[category]["correct"] += 1

            top_result_summary = (
                f"{retrieval_res.results[0].symbol_name} ({retrieval_res.results[0].file_path}) score={retrieval_res.results[0].original_score}"
                if retrieval_res.results
                else "None"
            )

            detailed_records.append({
                "query_id": qid,
                "repo_name": repo_id,
                "category": category,
                "query": query_text,
                "should_abstain": should_abstain,
                "did_abstain": did_abstain,
                "evidence_sufficiency": sufficiency.value,
                "is_correct": is_correct,
                "total_results": len(retrieval_res.results),
                "graph_evidence_count": len(retrieval_res.graph_evidence),
                "top_result": top_result_summary,
            })

        # Calculate metrics
        total_oos = len(out_of_scope_queries)
        total_ans = len(answerable_queries)

        abstention_precision = (
            true_abstentions / (true_abstentions + false_abstentions)
            if (true_abstentions + false_abstentions) > 0
            else 0.0
        )
        abstention_recall = (
            true_abstentions / (true_abstentions + false_answers)
            if (true_abstentions + false_answers) > 0
            else 0.0
        )
        false_answer_rate = (
            false_answers / total_oos
            if total_oos > 0
            else 0.0
        )
        false_abstention_rate = (
            false_abstentions / total_ans
            if total_ans > 0
            else 0.0
        )
        overall_accuracy = (
            (true_abstentions + true_answers) / total_queries
            if total_queries > 0
            else 0.0
        )

        category_summaries = {}
        for cat, counts in category_results.items():
            tot = counts["total"]
            category_summaries[cat] = {
                "total": tot,
                "correct": counts["correct"],
                "accuracy": round(counts["correct"] / tot, 4) if tot > 0 else 0.0,
                "abstained": counts["abstained"],
                "abstention_rate": round(counts["abstained"] / tot, 4) if tot > 0 else 0.0,
            }

        return {
            "summary": {
                "total_queries": total_queries,
                "out_of_scope_queries_count": total_oos,
                "answerable_control_queries_count": total_ans,
                "true_abstentions": true_abstentions,
                "false_answers": false_answers,
                "true_answers": true_answers,
                "false_abstentions": false_abstentions,
                "abstention_precision": round(abstention_precision, 4),
                "abstention_recall": round(abstention_recall, 4),
                "false_answer_rate": round(false_answer_rate, 4),
                "false_abstention_rate": round(false_abstention_rate, 4),
                "overall_accuracy": round(overall_accuracy, 4),
            },
            "evidence_sufficiency_distribution": {
                k: {
                    "count": v,
                    "percentage": round((v / total_queries) * 100, 2) if total_queries > 0 else 0.0,
                }
                for k, v in sufficiency_counts.items()
            },
            "category_breakdown": category_summaries,
            "detailed_records": detailed_records,
        }


abstention_benchmark_runner = AbstentionBenchmarkRunner()
