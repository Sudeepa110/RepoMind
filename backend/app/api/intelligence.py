"""
Advanced Repository Intelligence API Endpoints (Phase 8).
Exposes REST endpoints for Change Impact Analysis, Execution Flow Tracing,
Dependency Coupling, Bug Investigation, Risk Assessment, Test Recommendations,
and Technical Documentation.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.session import get_db
from backend.app.database.models import RepositoryModel
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
from backend.app.intelligence.intelligence_orchestrator import (
    intelligence_orchestrator,
)

router = APIRouter(prefix="/repositories/{repository_id}/intelligence", tags=["Advanced Intelligence"])


async def _verify_repo(repository_id: str, db: AsyncSession) -> RepositoryModel:
    stmt = select(RepositoryModel).where(RepositoryModel.id == repository_id)
    result = await db.execute(stmt)
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found.",
        )
    return repo


@router.post("/impact-analysis", response_model=ImpactAnalysisResult)
async def analyze_impact_endpoint(
    repository_id: str,
    request: ImpactAnalysisRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Evaluates multi-file code change impacts for a given symbol or file.
    Categorizes affected entities into DIRECT, INDIRECT, STRUCTURAL, and POTENTIAL.
    """
    await _verify_repo(repository_id, db)
    return await intelligence_orchestrator.analyze_impact(repository_id, request, db=db)


@router.post("/execution-flow", response_model=ExecutionFlowResult)
async def trace_execution_flow_endpoint(
    repository_id: str,
    request: ExecutionFlowRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Traces cross-file static invocation sequences starting from an entry point.
    """
    await _verify_repo(repository_id, db)
    return await intelligence_orchestrator.trace_execution_flow(repository_id, request, db=db)


@router.post("/dependencies", response_model=DependencyAnalysisResult)
async def analyze_dependencies_endpoint(
    repository_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Computes component coupling metrics, Martin's instability indices,
    tightly coupled modules, and architectural layer distribution.
    """
    await _verify_repo(repository_id, db)
    return await intelligence_orchestrator.analyze_dependencies(repository_id, db=db)


@router.post("/bug-investigation", response_model=BugInvestigationResult)
async def investigate_bugs_endpoint(
    repository_id: str,
    request: BugInvestigationRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Evidence-backed bug investigation detecting error handling omissions,
    null safety risks, resource leaks, and unresolved calls.
    """
    await _verify_repo(repository_id, db)
    return await intelligence_orchestrator.investigate_bugs(repository_id, request, db=db)


@router.post("/risk-assessment", response_model=RiskAssessmentResult)
async def assess_risk_endpoint(
    repository_id: str,
    request: RiskAssessmentRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Calculates deterministic risk scores for code changes based on blast radius,
    multi-hop propagation, API exposure, and core models.
    """
    await _verify_repo(repository_id, db)
    return await intelligence_orchestrator.assess_risk(repository_id, request, db=db)


@router.post("/test-recommendations", response_model=TestRecommendationsResult)
async def recommend_tests_endpoint(
    repository_id: str,
    request: TestRecommendationsRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Discovers existing tests and generates targeted unit, integration,
    and regression test recommendations with suggested assertions.
    """
    await _verify_repo(repository_id, db)
    return await intelligence_orchestrator.recommend_tests(repository_id, request, db=db)


@router.post("/documentation", response_model=DocumentationResult)
async def generate_documentation_endpoint(
    repository_id: str,
    request: DocumentationRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generates grounded technical documentation for symbols, modules,
    or endpoints with verified citations.
    """
    await _verify_repo(repository_id, db)
    return await intelligence_orchestrator.generate_documentation(repository_id, request, db=db)
