"""
RepoMind Advanced Intelligence Package (Phase 8).
Exports the unified intelligence orchestrator and specialized analyzers.
"""

from backend.app.intelligence.intelligence_models import (
    ImpactCategory,
    AffectedEntity,
    ImpactAnalysisRequest,
    ImpactAnalysisResult,
    ExecutionFlowStep,
    ExecutionFlowRequest,
    ExecutionFlowResult,
    DependencyCouplingMetric,
    DependencyAnalysisResult,
    BugSeverity,
    BugCategory,
    BugFinding,
    BugInvestigationRequest,
    BugInvestigationResult,
    RiskFactorBreakdown,
    RiskAssessmentRequest,
    RiskAssessmentResult,
    TestType,
    TestRecommendation,
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
from backend.app.intelligence.intelligence_orchestrator import (
    IntelligenceOrchestrator,
    intelligence_orchestrator,
)

__all__ = [
    "ImpactCategory",
    "AffectedEntity",
    "ImpactAnalysisRequest",
    "ImpactAnalysisResult",
    "ExecutionFlowStep",
    "ExecutionFlowRequest",
    "ExecutionFlowResult",
    "DependencyCouplingMetric",
    "DependencyAnalysisResult",
    "BugSeverity",
    "BugCategory",
    "BugFinding",
    "BugInvestigationRequest",
    "BugInvestigationResult",
    "RiskFactorBreakdown",
    "RiskAssessmentRequest",
    "RiskAssessmentResult",
    "TestType",
    "TestRecommendation",
    "TestRecommendationsRequest",
    "TestRecommendationsResult",
    "DocumentationRequest",
    "DocumentationResult",
    "ChangeImpactAnalyzer",
    "change_impact_analyzer",
    "ExecutionFlowTracer",
    "execution_flow_tracer",
    "DependencyAnalyzer",
    "dependency_analyzer",
    "BugInvestigator",
    "bug_investigator",
    "RiskAssessor",
    "risk_assessor",
    "TestRecommender",
    "test_recommender",
    "TechnicalDocumentationGenerator",
    "documentation_generator",
    "IntelligenceOrchestrator",
    "intelligence_orchestrator",
]
