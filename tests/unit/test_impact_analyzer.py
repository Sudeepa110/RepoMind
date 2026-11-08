"""
Unit tests for Change Impact Analyzer (Phase 8).
Verifies direct, indirect, structural, and potential impact classification,
bounded traversal depth, cycle resistance, blast radius, and risk computation.
"""

import tempfile
from pathlib import Path
import pytest

from backend.app.graph.interfaces import (
    GraphNode,
    GraphEdge,
    NodeType,
    RelationshipType,
)
from backend.app.graph.networkx_store import NetworkXGraphStore
from backend.app.intelligence.impact_analyzer import ChangeImpactAnalyzer
from backend.app.intelligence.intelligence_models import (
    ImpactAnalysisRequest,
    ImpactCategory,
)
from backend.app.intelligence.risk_assessor import RiskAssessor


@pytest.fixture
def test_graph_and_analyzer():
    """Sets up a mock knowledge graph with direct, indirect, and cyclic dependencies."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        store = NetworkXGraphStore(persist_dir=Path(tmp_dir))
        repo_id = "test_repo"

        # Nodes
        n_api = GraphNode(
            id="test_repo:backend/api/users.py:get_user_endpoint",
            repository_id=repo_id,
            type=NodeType.FUNCTION,
            name="get_user_endpoint",
            file_path="backend/api/users.py",
            start_line=10,
            end_line=25,
        )
        n_service = GraphNode(
            id="test_repo:backend/services/user_service.py:fetch_user_profile",
            repository_id=repo_id,
            type=NodeType.FUNCTION,
            name="fetch_user_profile",
            file_path="backend/services/user_service.py",
            start_line=30,
            end_line=50,
        )
        n_repo = GraphNode(
            id="test_repo:backend/db/user_repo.py:query_user_by_id",
            repository_id=repo_id,
            type=NodeType.FUNCTION,
            name="query_user_by_id",
            file_path="backend/db/user_repo.py",
            start_line=15,
            end_line=35,
        )
        n_model = GraphNode(
            id="test_repo:backend/models/user.py:UserModel",
            repository_id=repo_id,
            type=NodeType.CLASS,
            name="UserModel",
            file_path="backend/models/user.py",
            start_line=5,
            end_line=40,
        )
        n_helper = GraphNode(
            id="test_repo:backend/utils/formatters.py:format_user_dto",
            repository_id=repo_id,
            type=NodeType.FUNCTION,
            name="format_user_dto",
            file_path="backend/utils/formatters.py",
            start_line=10,
            end_line=20,
        )

        for n in [n_api, n_service, n_repo, n_model, n_helper]:
            store.add_node(n)

        # Edges:
        # get_user_endpoint -> CALLS -> fetch_user_profile
        store.add_edge(GraphEdge(
            source_id=n_api.id,
            target_id=n_service.id,
            relationship=RelationshipType.CALLS,
            repository_id=repo_id,
            confidence=1.0,
            is_confirmed=True,
            resolution_status="CONFIRMED",
        ))

        # fetch_user_profile -> CALLS -> query_user_by_id
        store.add_edge(GraphEdge(
            source_id=n_service.id,
            target_id=n_repo.id,
            relationship=RelationshipType.CALLS,
            repository_id=repo_id,
            confidence=1.0,
            is_confirmed=True,
            resolution_status="CONFIRMED",
        ))

        # Cyclic edge: query_user_by_id -> CALLS -> fetch_user_profile (recursive/mutual)
        store.add_edge(GraphEdge(
            source_id=n_repo.id,
            target_id=n_service.id,
            relationship=RelationshipType.CALLS,
            repository_id=repo_id,
            confidence=0.9,
            is_confirmed=True,
            resolution_status="CONFIRMED",
        ))

        # Structural edge: UserModel -> CONTAINS -> query_user_by_id
        store.add_edge(GraphEdge(
            source_id=n_model.id,
            target_id=n_repo.id,
            relationship=RelationshipType.CONTAINS,
            repository_id=repo_id,
            confidence=1.0,
            is_confirmed=True,
            resolution_status="CONFIRMED",
        ))

        # Unresolved dynamic edge to helper
        store.add_edge(GraphEdge(
            source_id=n_service.id,
            target_id=n_helper.id,
            relationship=RelationshipType.CALLS,
            repository_id=repo_id,
            confidence=0.5,
            is_confirmed=False,
            resolution_status="UNRESOLVED",
        ))

        analyzer = ChangeImpactAnalyzer(store=store, assessor=RiskAssessor(store=store))
        yield repo_id, analyzer


@pytest.mark.asyncio
async def test_direct_and_indirect_impact_classification(test_graph_and_analyzer):
    repo_id, analyzer = test_graph_and_analyzer

    # Analyze impact of changing `query_user_by_id`
    # Direct caller: `fetch_user_profile`
    # Indirect caller: `get_user_endpoint`
    # Structural: `UserModel`
    req = ImpactAnalysisRequest(target_symbol="query_user_by_id", max_depth=3)
    result = await analyzer.analyze(repo_id, req)

    assert result.target_symbol == "query_user_by_id"
    assert result.direct_count >= 1

    # Check direct caller
    direct_names = [e.name for e in result.affected_entities if e.category == ImpactCategory.DIRECT]
    assert "fetch_user_profile" in direct_names

    # Check indirect caller
    indirect_names = [e.name for e in result.affected_entities if e.category == ImpactCategory.INDIRECT]
    assert "get_user_endpoint" in indirect_names

    # Check structural relation
    structural_names = [e.name for e in result.affected_entities if e.category == ImpactCategory.STRUCTURAL]
    assert "UserModel" in structural_names

    # Check file blast radius includes multiple distinct files
    assert result.total_affected_files >= 3
    assert "backend/db/user_repo.py" in result.affected_files
    assert "backend/services/user_service.py" in result.affected_files


@pytest.mark.asyncio
async def test_cycle_resistance(test_graph_and_analyzer):
    """Verifies that mutual cycles do not cause infinite loops or duplicate infinite entries."""
    repo_id, analyzer = test_graph_and_analyzer

    req = ImpactAnalysisRequest(target_symbol="fetch_user_profile", max_depth=5)
    result = await analyzer.analyze(repo_id, req)

    assert result.target_symbol == "fetch_user_profile"
    # Entities should not contain duplicate symbol IDs
    ids = [e.symbol_id for e in result.affected_entities]
    assert len(ids) == len(set(ids)), "Duplicate entity was traversed due to cycle!"


@pytest.mark.asyncio
async def test_depth_bounding(test_graph_and_analyzer):
    """Verifies that max_depth=1 only returns direct and structural impacts."""
    repo_id, analyzer = test_graph_and_analyzer

    req = ImpactAnalysisRequest(target_symbol="query_user_by_id", max_depth=1)
    result = await analyzer.analyze(repo_id, req)

    # With depth 1, indirect caller `get_user_endpoint` should NOT be included
    indirect_names = [e.name for e in result.affected_entities if e.category == ImpactCategory.INDIRECT]
    assert "get_user_endpoint" not in indirect_names
    assert result.indirect_count == 0


@pytest.mark.asyncio
async def test_missing_symbol_fallback(test_graph_and_analyzer):
    """Verifies graceful handling of non-existent symbols."""
    repo_id, analyzer = test_graph_and_analyzer

    req = ImpactAnalysisRequest(target_symbol="non_existent_function_xyz", max_depth=3)
    result = await analyzer.analyze(repo_id, req)

    assert result.total_affected_symbols == 0
    assert "could not be located" in result.explanation
    assert len(result.limitations) > 0
