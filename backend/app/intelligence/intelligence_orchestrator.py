"""
Unified Intelligence Orchestrator (Phase 8).
Coordinates multi-file change impact analysis, execution flow tracing, architectural dependencies,
bug investigation, risk assessment, test recommendations, and technical documentation.
"""

import logging
from typing import Dict, Any, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.session import AsyncSessionLocal
from backend.app.database.models import RepositoryModel
from backend.app.graph.networkx_store import networkx_graph_store
from backend.app.intelligence.intelligence_models import (
    ImpactAnalysisRequest,
    ImpactAnalysisResult,
    ExecutionFlowRequest,
    ExecutionFlowResult,
    DependencyAnalysisResult,
    BugInvestigationRequest,
    BugInvestigationResult,
    RiskAssessmentRequest,
    RiskAssessmentResult,
    TestRecommendationsRequest,
    TestRecommendationsResult,
    DocumentationRequest,
    DocumentationResult,
)
from backend.app.intelligence.impact_analyzer import ChangeImpactAnalyzer, change_impact_analyzer
from backend.app.intelligence.execution_flow import ExecutionFlowTracer, execution_flow_tracer
from backend.app.intelligence.dependency_analyzer import DependencyAnalyzer, dependency_analyzer
from backend.app.intelligence.bug_investigator import BugInvestigator, bug_investigator
from backend.app.intelligence.risk_assessor import RiskAssessor, risk_assessor
from backend.app.intelligence.test_recommender import TestRecommender, test_recommender
from backend.app.intelligence.documentation_generator import (
    TechnicalDocumentationGenerator,
    documentation_generator,
)

logger = logging.getLogger(__name__)


class IntelligenceOrchestrator:
    """
    Central orchestration service for Phase 8 advanced intelligence operations.
    """

    def __init__(
        self,
        impact_analyzer: Optional[ChangeImpactAnalyzer] = None,
        flow_tracer: Optional[ExecutionFlowTracer] = None,
        dep_analyzer: Optional[DependencyAnalyzer] = None,
        bug_detector: Optional[BugInvestigator] = None,
        risk_service: Optional[RiskAssessor] = None,
        test_gen: Optional[TestRecommender] = None,
        doc_gen: Optional[TechnicalDocumentationGenerator] = None,
    ):
        self.impact_analyzer = impact_analyzer or change_impact_analyzer
        self.flow_tracer = flow_tracer or execution_flow_tracer
        self.dep_analyzer = dep_analyzer or dependency_analyzer
        self.bug_detector = bug_detector or bug_investigator
        self.risk_service = risk_service or risk_assessor
        self.test_gen = test_gen or test_recommender
        self.doc_gen = doc_gen or documentation_generator

    async def _verify_repository(
        self, repository_id: str, db: Optional[AsyncSession] = None
    ) -> bool:
        """Verifies repository existence in database or graph store."""
        # 1. Check graph store
        stats = networkx_graph_store.get_stats(repository_id)
        if stats.get("total_nodes", 0) > 0:
            return True

        # 2. Check DB
        if db:
            result = await db.execute(select(RepositoryModel).where(RepositoryModel.id == repository_id))
            repo = result.scalar_one_or_none()
            if repo:
                return True
        else:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(RepositoryModel).where(RepositoryModel.id == repository_id))
                repo = result.scalar_one_or_none()
                if repo:
                    return True

        return False

    async def analyze_impact(
        self,
        repository_id: str,
        request: ImpactAnalysisRequest,
        db: Optional[AsyncSession] = None,
    ) -> ImpactAnalysisResult:
        exists = await self._verify_repository(repository_id, db)
        if not exists:
            return ImpactAnalysisResult(
                target_symbol=request.target_symbol,
                target_file=request.file_path,
                explanation=f"Repository '{repository_id}' is not indexed or knowledge graph is empty.",
                limitations=["Repository knowledge graph not initialized."],
            )
        return await self.impact_analyzer.analyze(repository_id, request)

    async def trace_execution_flow(
        self,
        repository_id: str,
        request: ExecutionFlowRequest,
        db: Optional[AsyncSession] = None,
    ) -> ExecutionFlowResult:
        exists = await self._verify_repository(repository_id, db)
        if not exists:
            return ExecutionFlowResult(
                entry_point=request.entry_point,
                explanation=f"Repository '{repository_id}' is not indexed or knowledge graph is empty.",
                limitations=["Repository knowledge graph not initialized."],
            )
        return await self.flow_tracer.trace_flow(repository_id, request)

    async def analyze_dependencies(
        self,
        repository_id: str,
        db: Optional[AsyncSession] = None,
    ) -> DependencyAnalysisResult:
        exists = await self._verify_repository(repository_id, db)
        if not exists:
            return DependencyAnalysisResult(
                summary=f"Repository '{repository_id}' is not indexed or knowledge graph is empty."
            )
        return self.dep_analyzer.analyze(repository_id)

    async def investigate_bugs(
        self,
        repository_id: str,
        request: BugInvestigationRequest,
        db: Optional[AsyncSession] = None,
    ) -> BugInvestigationResult:
        exists = await self._verify_repository(repository_id, db)
        if not exists:
            return BugInvestigationResult(
                target=request.target,
                explanation=f"Repository '{repository_id}' is not indexed or knowledge graph is empty.",
                limitations=["Repository knowledge graph not initialized."],
            )
        return await self.bug_detector.investigate(repository_id, request)

    async def assess_risk(
        self,
        repository_id: str,
        request: RiskAssessmentRequest,
        db: Optional[AsyncSession] = None,
    ) -> RiskAssessmentResult:
        exists = await self._verify_repository(repository_id, db)
        if not exists:
            return RiskAssessmentResult(
                target_symbol=request.target_symbol,
                summary=f"Repository '{repository_id}' is not indexed or knowledge graph is empty.",
            )

        # Leverage impact analyzer to get the entities
        impact = await self.impact_analyzer.analyze(
            repository_id,
            ImpactAnalysisRequest(
                target_symbol=request.target_symbol,
                file_path=request.file_path,
                max_depth=3,
            )
        )

        target_node = self.impact_analyzer._resolve_target(
            repository_id, request.target_symbol, request.file_path
        )

        direct_entities = [e for e in impact.affected_entities if e.category.value == "DIRECT"]
        indirect_entities = [e for e in impact.affected_entities if e.category.value == "INDIRECT"]

        return self.risk_service.calculate_risk(
            target_name=request.target_symbol,
            target_file=request.file_path or (target_node.file_path if target_node else None),
            direct_entities=direct_entities,
            indirect_entities=indirect_entities,
            affected_files=impact.affected_files,
            unresolved_count=impact.potential_count,
            target_node=target_node,
        )

    async def recommend_tests(
        self,
        repository_id: str,
        request: TestRecommendationsRequest,
        db: Optional[AsyncSession] = None,
    ) -> TestRecommendationsResult:
        exists = await self._verify_repository(repository_id, db)
        if not exists:
            return TestRecommendationsResult(
                target_symbol=request.target_symbol,
                summary=f"Repository '{repository_id}' is not indexed or knowledge graph is empty.",
            )
        return await self.test_gen.recommend(repository_id, request)

    async def generate_documentation(
        self,
        repository_id: str,
        request: DocumentationRequest,
        db: Optional[AsyncSession] = None,
    ) -> DocumentationResult:
        exists = await self._verify_repository(repository_id, db)
        if not exists:
            return DocumentationResult(
                target_name=request.target,
                target_type="Unknown",
                file_path=request.file_path or "",
                markdown_documentation=f"Repository '{repository_id}' is not indexed.",
                citations=[],
            )
        return await self.doc_gen.generate_doc(repository_id, request)


intelligence_orchestrator = IntelligenceOrchestrator()
