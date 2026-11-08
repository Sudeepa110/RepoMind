"""
Unified Hybrid Retrieval API endpoints.
Provides repository-scoped hybrid search combining Vector RAG, GraphRAG,
and Keyword BM25 search with Reciprocal Rank Fusion and assembled context.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.session import get_db
from backend.app.database.models import RepositoryModel
from backend.app.retrieval.retrieval_models import (
    HybridSearchRequest,
    HybridRetrievalResponse,
    QueryAnalysisResult,
)
from backend.app.retrieval.query_analyzer import query_analyzer
from backend.app.retrieval.hybrid_retriever import hybrid_retriever

router = APIRouter(prefix="/repositories/{repository_id}", tags=["Hybrid Retrieval"])


async def _verify_repository_exists(repository_id: str, db: AsyncSession) -> RepositoryModel:
    stmt = select(RepositoryModel).where(RepositoryModel.id == repository_id)
    result = await db.execute(stmt)
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found.",
        )
    return repo


@router.post("/hybrid-search", response_model=HybridRetrievalResponse)
async def hybrid_search_endpoint(
    repository_id: str,
    request: HybridSearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Execute unified hybrid retrieval combining Vector RAG, GraphRAG, and Keyword Search.
    Ranks candidates via Reciprocal Rank Fusion (RRF) and returns assembled context with citations.
    """
    await _verify_repository_exists(repository_id, db)
    response = hybrid_retriever.hybrid_search(repository_id, request)
    return response


@router.post("/analyze-query", response_model=QueryAnalysisResult)
async def analyze_query_endpoint(
    repository_id: str,
    request: HybridSearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Diagnostic endpoint: analyzes developer query, extracts symbols/intents, and returns routing recommendations.
    """
    await _verify_repository_exists(repository_id, db)
    analysis = query_analyzer.analyze(request.query)
    return analysis

