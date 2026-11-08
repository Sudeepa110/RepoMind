"""
Deterministic Risk Assessor (Phase 8).
Calculates an objective, transparent, repeatable risk score for code changes based on
dependency blast radius, multi-file propagation, API/model criticality, and unresolved edges.
"""

from typing import List, Dict, Any, Optional
from backend.app.intelligence.intelligence_models import (
    RiskAssessmentResult,
    RiskFactorBreakdown,
    AffectedEntity,
    ImpactCategory,
)
from backend.app.graph.interfaces import BaseGraphStore, GraphNode
from backend.app.graph.networkx_store import networkx_graph_store


class RiskAssessor:
    """
    Deterministic risk evaluation engine for repository changes.
    """

    def __init__(self, store: Optional[BaseGraphStore] = None):
        self.store = store or networkx_graph_store

    def is_api_component(self, node: Optional[GraphNode], file_path: Optional[str]) -> bool:
        """Determines if a node or file represents an external-facing API endpoint or router."""
        path = (file_path or "").lower().replace("\\", "/")
        api_indicators = ["/api/", "routes", "endpoints", "controllers", "views", "handlers"]
        if any(ind in path for ind in api_indicators):
            return True
        if node and node.name:
            name = node.name.lower()
            if any(name.startswith(p) for p in ["get_", "post_", "put_", "delete_", "patch_"]) and "api" in path:
                return True
        return False

    def is_model_component(self, node: Optional[GraphNode], file_path: Optional[str]) -> bool:
        """Determines if a node or file represents a core data model or schema."""
        path = (file_path or "").lower().replace("\\", "/")
        model_indicators = ["models", "schemas", "entities", "domain", "records"]
        return any(ind in path for ind in model_indicators)

    def calculate_risk(
        self,
        target_name: str,
        target_file: Optional[str],
        direct_entities: List[AffectedEntity],
        indirect_entities: List[AffectedEntity],
        affected_files: List[str],
        unresolved_count: int = 0,
        target_node: Optional[GraphNode] = None,
    ) -> RiskAssessmentResult:
        """
        Calculates deterministic risk score according to standard RepoMind risk formula:
        Score = min(100, 15*N_direct + 5*N_indirect + 20*is_api + 15*is_model + 10*N_files + 5*N_unresolved)
        """
        n_direct = len(direct_entities)
        n_indirect = len(indirect_entities)
        n_files = len(affected_files)

        is_api = self.is_api_component(target_node, target_file) or any(
            self.is_api_component(None, e.file_path) for e in direct_entities
        )
        is_model = self.is_model_component(target_node, target_file) or any(
            self.is_model_component(None, e.file_path) for e in direct_entities
        )

        breakdown: List[RiskFactorBreakdown] = []

        # 1. Direct callers / dependents
        pts_direct = 15.0 * n_direct
        breakdown.append(RiskFactorBreakdown(
            factor_name="Direct Dependents",
            points=pts_direct,
            reason=f"{n_direct} direct callers or importers depend immediately on this symbol (15 pts each)."
        ))

        # 2. Indirect callers / propagation
        pts_indirect = 5.0 * n_indirect
        breakdown.append(RiskFactorBreakdown(
            factor_name="Indirect Multi-hop Propagation",
            points=pts_indirect,
            reason=f"{n_indirect} secondary/transitive dependents reached via multi-hop call chains (5 pts each)."
        ))

        # 3. Public API Exposure
        pts_api = 20.0 if is_api else 0.0
        breakdown.append(RiskFactorBreakdown(
            factor_name="Public API Exposure",
            points=pts_api,
            reason="Component or its direct dependents are exposed in API endpoints/controllers (20 pts)." if is_api else "No immediate public API exposure identified (0 pts)."
        ))

        # 4. Core Data Model Impact
        pts_model = 15.0 if is_model else 0.0
        breakdown.append(RiskFactorBreakdown(
            factor_name="Core Data Model Impact",
            points=pts_model,
            reason="Component defines or alters core database/domain data models (15 pts)." if is_model else "Not a primary data model (0 pts)."
        ))

        # 5. File Blast Radius
        pts_files = 10.0 * n_files
        breakdown.append(RiskFactorBreakdown(
            factor_name="File Blast Radius",
            points=pts_files,
            reason=f"Modifications propagate across {n_files} distinct files across the repository (10 pts each)."
        ))

        # 6. Unresolved / Dynamic dependencies
        pts_unresolved = 5.0 * unresolved_count
        if unresolved_count > 0:
            breakdown.append(RiskFactorBreakdown(
                factor_name="Dynamic / Unresolved Call Uncertainty",
                points=pts_unresolved,
                reason=f"{unresolved_count} unresolved dynamic calls detected in traversal path (5 pts each)."
            ))

        raw_score = pts_direct + pts_indirect + pts_api + pts_model + pts_files + pts_unresolved
        final_score = min(100.0, float(raw_score))

        if final_score >= 81.0:
            level = "CRITICAL"
        elif final_score >= 56.0:
            level = "HIGH"
        elif final_score >= 26.0:
            level = "MEDIUM"
        else:
            level = "LOW"

        summary = (
            f"Calculated risk level is {level} (Score: {final_score:.1f}/100). "
            f"Affects {n_files} file(s) with {n_direct} direct and {n_indirect} indirect dependent(s)."
        )

        formula_explanation = (
            "RiskScore = min(100, 15*N_direct + 5*N_indirect + 20*is_api + 15*is_model + 10*N_files + 5*N_unresolved). "
            "Risk tiers: 0-25 LOW, 26-55 MEDIUM, 56-80 HIGH, 81-100 CRITICAL."
        )

        return RiskAssessmentResult(
            target_symbol=target_name,
            target_file=target_file,
            risk_score=final_score,
            risk_level=level,
            blast_radius_files=n_files,
            direct_dependents=n_direct,
            indirect_dependents=n_indirect,
            is_public_api=is_api,
            is_core_model=is_model,
            formula_breakdown=breakdown,
            summary=summary,
            citations=[],
            formula_explanation=formula_explanation,
        )


risk_assessor = RiskAssessor()
