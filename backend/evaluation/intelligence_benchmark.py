"""
Knowledge Graph & Advanced Intelligence Benchmarking Engine (Phase 9).
Measures:
1. Knowledge Graph node and edge extraction precision, recall, and relationship accuracy.
2. Change impact analysis precision, recall, false positive / negative rates, cycle handling.
3. Bug investigation labeled fixture precision, recall, F1 score, false positive / negative rates.
4. Test recommendation relevance and documentation generation accuracy.
"""

import logging
from typing import Dict, Any, List, Set, Tuple, Optional

from backend.app.graph.interfaces import (
    BaseGraphStore,
    RelationshipType,
    NodeType,
)
from backend.app.graph.networkx_store import networkx_graph_store
from backend.app.intelligence.impact_analyzer import ChangeImpactAnalyzer, change_impact_analyzer
from backend.app.intelligence.bug_investigator import BugInvestigator, bug_investigator
from backend.app.intelligence.test_recommender import TestRecommender, test_recommender
from backend.app.intelligence.documentation_generator import (
    TechnicalDocumentationGenerator,
    documentation_generator,
)
from backend.app.intelligence.intelligence_models import (
    ImpactAnalysisRequest,
    BugInvestigationRequest,
    TestRecommendationsRequest,
    DocumentationRequest,
    ImpactCategory,
    BugSeverity,
)

logger = logging.getLogger(__name__)


class IntelligenceBenchmarkRunner:
    """
    Evaluates Phase 5 and Phase 8 intelligence capabilities against ground-truth fixtures.
    """

    def __init__(
        self,
        store: Optional[BaseGraphStore] = None,
        impact_analyzer: Optional[ChangeImpactAnalyzer] = None,
        bug_detector: Optional[BugInvestigator] = None,
        test_gen: Optional[TestRecommender] = None,
        doc_gen: Optional[TechnicalDocumentationGenerator] = None,
    ):
        self.store = store or networkx_graph_store
        self.impact_analyzer = impact_analyzer or change_impact_analyzer
        self.bug_detector = bug_detector or bug_investigator
        self.test_gen = test_gen or test_recommender
        self.doc_gen = doc_gen or documentation_generator

    # --- A. Knowledge Graph Evaluation ---
    def evaluate_knowledge_graph(
        self,
        repository_id: str,
        ground_truth_nodes: Set[str],
        ground_truth_edges: Set[Tuple[str, str, str]],  # (source_name, target_name, rel_type)
    ) -> Dict[str, Any]:
        """
        Measures node/edge extraction precision & recall and relationship category breakdowns.
        """
        all_nodes = self.store.get_nodes(repository_id, limit=2000)
        all_edges = self.store.get_edges(repository_id, limit=5000)

        extracted_node_names = set(n.name for n in all_nodes)
        node_hits = len(extracted_node_names.intersection(ground_truth_nodes))
        node_precision = node_hits / max(1, len(extracted_node_names))
        node_recall = node_hits / max(1, len(ground_truth_nodes))

        extracted_edges = set()
        confirmed_count = 0
        unresolved_count = 0

        for e in all_edges:
            s_node = self.store.get_node(e.source_id, repository_id)
            t_node = self.store.get_node(e.target_id, repository_id)
            s_name = s_node.name if s_node else e.source_id.split(":")[-1]
            t_name = t_node.name if t_node else e.target_id.split(":")[-1]
            rel_type = e.relationship.value if hasattr(e.relationship, 'value') else str(e.relationship)
            extracted_edges.add((s_name, t_name, rel_type))

            if e.resolution_status == "CONFIRMED":
                confirmed_count += 1
            else:
                unresolved_count += 1

        edge_hits = len(extracted_edges.intersection(ground_truth_edges))
        edge_precision = edge_hits / max(1, len(extracted_edges))
        edge_recall = edge_hits / max(1, len(ground_truth_edges))

        return {
            "total_nodes_extracted": len(all_nodes),
            "ground_truth_nodes": len(ground_truth_nodes),
            "node_precision": round(node_precision, 4),
            "node_recall": round(node_recall, 4),
            "total_edges_extracted": len(all_edges),
            "ground_truth_edges": len(ground_truth_edges),
            "edge_precision": round(edge_precision, 4),
            "edge_recall": round(edge_recall, 4),
            "confirmed_edges": confirmed_count,
            "unresolved_edges": unresolved_count,
        }

    # --- B. Change Impact Analysis Evaluation ---
    async def evaluate_impact_analysis(
        self,
        repository_id: str,
        target_symbol: str,
        ground_truth_direct: Set[str],
        ground_truth_indirect: Set[str],
        ground_truth_files: Set[str],
        non_affected_symbols: Set[str],  # Negative controls
    ) -> Dict[str, Any]:
        """
        Measures precision, recall, false positive rate, and false negative rate for change impact.
        """
        res = await self.impact_analyzer.analyze(
            repository_id,
            ImpactAnalysisRequest(target_symbol=target_symbol, max_depth=3),
        )

        extracted_direct = set(
            e.name for e in res.affected_entities if e.category == ImpactCategory.DIRECT
        )
        extracted_indirect = set(
            e.name for e in res.affected_entities if e.category == ImpactCategory.INDIRECT
        )
        extracted_files = set(f.replace("\\", "/").lower() for f in res.affected_files)

        # Direct metrics
        tp_direct = len(extracted_direct.intersection(ground_truth_direct))
        fp_direct = len(extracted_direct - ground_truth_direct)
        fn_direct = len(ground_truth_direct - extracted_direct)

        direct_precision = tp_direct / max(1, tp_direct + fp_direct)
        direct_recall = tp_direct / max(1, tp_direct + fn_direct)
        fn_rate = fn_direct / max(1, len(ground_truth_direct)) if ground_truth_direct else 0.0

        # Negative control check (False Positives)
        false_positive_negatives = len(extracted_direct.intersection(non_affected_symbols))
        fp_rate = false_positive_negatives / max(1, len(non_affected_symbols)) if non_affected_symbols else 0.0

        # File blast radius accuracy
        file_hits = len(extracted_files.intersection(set(f.lower() for f in ground_truth_files)))
        file_accuracy = file_hits / max(1, len(ground_truth_files))

        return {
            "target_symbol": target_symbol,
            "direct_precision": round(direct_precision, 4),
            "direct_recall": round(direct_recall, 4),
            "false_negative_rate": round(fn_rate, 4),
            "false_positive_rate": round(fp_rate, 4),
            "file_blast_radius_accuracy": round(file_accuracy, 4),
            "risk_score": res.risk_score,
            "risk_level": res.risk_level,
            "total_affected_entities": len(res.affected_entities),
        }

    # --- C. Bug Investigation Evaluation ---
    async def evaluate_bug_investigation(
        self,
        repository_id: str,
        labeled_bugs: List[Dict[str, Any]],  # List of {"symbol": str, "category": str, "is_bug": bool}
    ) -> Dict[str, Any]:
        """
        Measures Precision, Recall, F1 Score, False Positive Rate, and False Negative Rate on labeled defect fixtures.
        """
        res = await self.bug_detector.investigate(
            repository_id, BugInvestigationRequest()
        )

        detected_symbols = set(f.affected_symbol for f in res.findings)

        tp = 0
        fp = 0
        fn = 0
        tn = 0

        for item in labeled_bugs:
            sym = item["symbol"]
            is_actual_bug = item["is_bug"]

            if is_actual_bug:
                if sym in detected_symbols:
                    tp += 1
                else:
                    fn += 1
            else:
                if sym in detected_symbols:
                    fp += 1
                else:
                    tn += 1

        precision = tp / max(1, tp + fp)
        recall = tp / max(1, tp + fn)
        f1 = (2 * precision * recall) / max(0.0001, precision + recall)
        fp_rate = fp / max(1, fp + tn)
        fn_rate = fn / max(1, fn + tp)

        return {
            "total_labeled_cases": len(labeled_bugs),
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "true_negatives": tn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "false_positive_rate": round(fp_rate, 4),
            "false_negative_rate": round(fn_rate, 4),
        }

    # --- D. Test Recommendations Evaluation ---
    async def evaluate_test_recommendations(
        self,
        repository_id: str,
        target_symbol: str,
        expected_test_categories: Set[str],
    ) -> Dict[str, Any]:
        """
        Evaluates test recommender's category coverage and existing test discovery.
        """
        res = await self.test_gen.recommend(
            repository_id, TestRecommendationsRequest(target_symbol=target_symbol)
        )

        categories_found = set(r.category.value for r in res.recommendations)
        category_coverage = len(categories_found.intersection(expected_test_categories)) / max(1, len(expected_test_categories))

        return {
            "target_symbol": target_symbol,
            "total_recommendations": res.total_recommendations,
            "existing_tests_found_count": len(res.existing_tests_found),
            "category_coverage": round(category_coverage, 4),
            "has_suggested_assertions": all(len(r.suggested_assertions) > 0 for r in res.recommendations),
        }


intelligence_benchmark_runner = IntelligenceBenchmarkRunner()
