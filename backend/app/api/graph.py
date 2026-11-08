"""
Knowledge Graph API endpoints.
Provides repository-scoped graph status, node/edge inspection, caller/callee traversal,
inheritance hierarchy, dependency inspection, execution paths, and impact analysis.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.session import get_db
from backend.app.database.models import RepositoryModel
from backend.app.graph.interfaces import NodeType, RelationshipType
from backend.app.graph.networkx_store import networkx_graph_store
from backend.app.graph.traversal import graph_traversal_service
from backend.app.schemas.graph import (
    GraphStatusResponse,
    GraphNodesResponse,
    GraphEdgesResponse,
    GraphNodeItem,
    GraphEdgeItem,
    CallersResponse,
    CalleesResponse,
    InheritanceHierarchyResponse,
    DependenciesResponse,
    ExecutionPathsResponse,
    ImpactAnalysisResponse,
    SubgraphResponse,
)

router = APIRouter(prefix="/repositories/{repository_id}/graph", tags=["Knowledge Graph"])


async def _verify_repository_exists(repository_id: str, db: AsyncSession) -> RepositoryModel:
    """Helper to verify repository exists and belongs to valid session."""
    stmt = select(RepositoryModel).where(RepositoryModel.id == repository_id)
    result = await db.execute(stmt)
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found.",
        )
    return repo


@router.get("/status", response_model=GraphStatusResponse)
async def get_graph_status(
    repository_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve knowledge graph status and summary statistics."""
    await _verify_repository_exists(repository_id, db)
    stats = networkx_graph_store.get_stats(repository_id)
    return GraphStatusResponse(**stats)


@router.get("/nodes", response_model=GraphNodesResponse)
async def get_graph_nodes(
    repository_id: str,
    node_type: Optional[str] = Query(None, description="Filter by NodeType (e.g. Function, Class, File)"),
    file_path: Optional[str] = Query(None, description="Filter by relative file path"),
    query: Optional[str] = Query(None, description="Search term matching node name"),
    limit: int = Query(50, ge=1, le=200, description="Max nodes to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve filtered and paginated nodes for a repository knowledge graph."""
    await _verify_repository_exists(repository_id, db)

    parsed_node_type: Optional[NodeType] = None
    if node_type:
        try:
            parsed_node_type = NodeType(node_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid node_type '{node_type}'. Valid types: {[t.value for t in NodeType]}",
            )

    nodes = networkx_graph_store.get_nodes(
        repository_id,
        node_type=parsed_node_type,
        file_path=file_path,
        query=query,
        limit=limit,
        offset=offset,
    )

    items = [
        GraphNodeItem(
            id=n.id,
            repository_id=n.repository_id,
            type=n.type.value,
            name=n.name,
            qualified_name=n.qualified_name,
            file_path=n.file_path,
            start_line=n.start_line,
            end_line=n.end_line,
            language=n.language,
            commit_hash=n.commit_hash,
            symbol_id=n.symbol_id,
            content_hash=n.content_hash,
            properties=n.properties,
        )
        for n in nodes
    ]

    return GraphNodesResponse(
        repository_id=repository_id,
        total=len(items),
        limit=limit,
        offset=offset,
        nodes=items,
    )


@router.get("/edges", response_model=GraphEdgesResponse)
async def get_graph_edges(
    repository_id: str,
    relationship: Optional[str] = Query(None, description="Filter by RelationshipType (e.g. CALLS, IMPORTS, CONTAINS)"),
    source_id: Optional[str] = Query(None, description="Filter by source node ID"),
    target_id: Optional[str] = Query(None, description="Filter by target node ID"),
    limit: int = Query(50, ge=1, le=200, description="Max edges to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve filtered and paginated edges for a repository knowledge graph."""
    await _verify_repository_exists(repository_id, db)

    parsed_rel: Optional[RelationshipType] = None
    if relationship:
        try:
            parsed_rel = RelationshipType(relationship)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid relationship '{relationship}'. Valid types: {[r.value for r in RelationshipType]}",
            )

    edges = networkx_graph_store.get_edges(
        repository_id,
        relationship=parsed_rel,
        source_id=source_id,
        target_id=target_id,
        limit=limit,
        offset=offset,
    )

    items = [
        GraphEdgeItem(
            source_id=e.source_id,
            target_id=e.target_id,
            relationship=e.relationship.value,
            repository_id=e.repository_id,
            is_confirmed=e.is_confirmed,
            confidence=e.confidence,
            resolution_status=e.resolution_status,
            properties=e.properties,
        )
        for e in edges
    ]

    return GraphEdgesResponse(
        repository_id=repository_id,
        total=len(items),
        limit=limit,
        offset=offset,
        edges=items,
    )


@router.get("/callers", response_model=CallersResponse)
async def get_callers(
    repository_id: str,
    symbol: str = Query(..., min_length=1, description="Target symbol name or node ID"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all callers of a function or method."""
    await _verify_repository_exists(repository_id, db)
    res = graph_traversal_service.find_callers(repository_id, symbol)
    return CallersResponse(**res)


@router.get("/callees", response_model=CalleesResponse)
async def get_callees(
    repository_id: str,
    symbol: str = Query(..., min_length=1, description="Source symbol name or node ID"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all callees called by a function or method."""
    await _verify_repository_exists(repository_id, db)
    res = graph_traversal_service.find_callees(repository_id, symbol)
    return CalleesResponse(**res)


@router.get("/inheritance", response_model=InheritanceHierarchyResponse)
async def get_inheritance(
    repository_id: str,
    symbol: str = Query(..., min_length=1, description="Class or Interface name or node ID"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve class inheritance and interface implementation hierarchy."""
    await _verify_repository_exists(repository_id, db)
    res = graph_traversal_service.find_inheritance_hierarchy(repository_id, symbol)
    return InheritanceHierarchyResponse(**res)


@router.get("/dependencies", response_model=DependenciesResponse)
async def get_dependencies(
    repository_id: str,
    target: str = Query(..., min_length=1, description="Symbol name or file path"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve direct imports and dependents of a module or file."""
    await _verify_repository_exists(repository_id, db)
    res = graph_traversal_service.find_dependencies(repository_id, target)
    return DependenciesResponse(**res)


@router.get("/paths", response_model=ExecutionPathsResponse)
async def get_execution_paths(
    repository_id: str,
    source: str = Query(..., min_length=1, description="Starting function/method name"),
    target: str = Query(..., min_length=1, description="Destination function/method name"),
    max_depth: int = Query(5, ge=1, le=10, description="Maximum call depth to traverse"),
    limit: int = Query(10, ge=1, le=50, description="Maximum distinct paths to return"),
    db: AsyncSession = Depends(get_db),
):
    """Explore bounded static execution invocation paths between two symbols."""
    await _verify_repository_exists(repository_id, db)
    res = graph_traversal_service.find_execution_paths(
        repository_id, source, target, max_depth=max_depth, limit=limit
    )
    return ExecutionPathsResponse(**res)


@router.get("/impact", response_model=ImpactAnalysisResponse)
async def get_impact_analysis(
    repository_id: str,
    target: str = Query(..., min_length=1, description="Symbol name or file path to analyze blast radius for"),
    depth: int = Query(2, ge=1, le=3, description="Blast radius traversal depth"),
    db: AsyncSession = Depends(get_db),
):
    """Analyze blast radius / impacted symbols when a node or file changes."""
    await _verify_repository_exists(repository_id, db)
    res = graph_traversal_service.analyze_impact(repository_id, target, depth=depth)
    return ImpactAnalysisResponse(**res)


@router.get("/subgraph", response_model=SubgraphResponse)
async def get_subgraph(
    repository_id: str,
    center_node_id: str = Query(..., min_length=1, description="Center node identifier"),
    radius: int = Query(1, ge=1, le=3, description="Neighborhood radius"),
    max_nodes: int = Query(50, ge=5, le=150, description="Max nodes to return in ego subgraph"),
    db: AsyncSession = Depends(get_db),
):
    """Extract ego subgraph around a target node for localized graph visualization."""
    await _verify_repository_exists(repository_id, db)
    res = networkx_graph_store.get_subgraph(center_node_id, radius=radius, max_nodes=max_nodes)
    return SubgraphResponse(**res)
