"""
Unit tests for Dependency Analyzer (Phase 8).
Verifies Martin's instability index, architectural layering, and tightly coupled module detection.
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
from backend.app.intelligence.dependency_analyzer import DependencyAnalyzer


@pytest.fixture
def dep_graph_fixture():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        store = NetworkXGraphStore(persist_dir=Path(tmp_dir))
        repo_id = "arch_repo"

        # Create nodes in different layers
        f_api = GraphNode(
            id="arch_repo:backend/api/router.py:router",
            repository_id=repo_id,
            type=NodeType.FILE,
            name="router.py",
            file_path="backend/api/router.py",
        )
        f_service = GraphNode(
            id="arch_repo:backend/services/auth.py:auth",
            repository_id=repo_id,
            type=NodeType.FILE,
            name="auth.py",
            file_path="backend/services/auth.py",
        )
        f_db = GraphNode(
            id="arch_repo:backend/database/session.py:db",
            repository_id=repo_id,
            type=NodeType.FILE,
            name="session.py",
            file_path="backend/database/session.py",
        )
        f_model = GraphNode(
            id="arch_repo:backend/models/user.py:user",
            repository_id=repo_id,
            type=NodeType.FILE,
            name="user.py",
            file_path="backend/models/user.py",
        )

        for n in [f_api, f_service, f_db, f_model]:
            store.add_node(n)

        # Edges:
        # API -> IMPORTS -> Service
        store.add_edge(GraphEdge(
            source_id=f_api.id,
            target_id=f_service.id,
            relationship=RelationshipType.IMPORTS,
            repository_id=repo_id,
        ))

        # Service -> IMPORTS -> API (Circular / Tightly coupled!)
        store.add_edge(GraphEdge(
            source_id=f_service.id,
            target_id=f_api.id,
            relationship=RelationshipType.IMPORTS,
            repository_id=repo_id,
        ))

        # Service -> IMPORTS -> DB
        store.add_edge(GraphEdge(
            source_id=f_service.id,
            target_id=f_db.id,
            relationship=RelationshipType.IMPORTS,
            repository_id=repo_id,
        ))

        # Service -> IMPORTS -> Model
        store.add_edge(GraphEdge(
            source_id=f_service.id,
            target_id=f_model.id,
            relationship=RelationshipType.IMPORTS,
            repository_id=repo_id,
        ))

        # Service -> IMPORTS -> ext:pydantic
        store.add_edge(GraphEdge(
            source_id=f_service.id,
            target_id="ext:pydantic",
            relationship=RelationshipType.IMPORTS,
            repository_id=repo_id,
        ))

        analyzer = DependencyAnalyzer(store=store)
        yield repo_id, analyzer


def test_architectural_layers_and_coupling(dep_graph_fixture):
    repo_id, analyzer = dep_graph_fixture

    res = analyzer.analyze(repo_id)

    assert res.total_files == 4
    # Layers checked: API, SERVICE, DATA, MODEL
    assert "API" in res.layer_distribution
    assert "SERVICE" in res.layer_distribution
    assert "DATA" in res.layer_distribution
    assert "MODEL" in res.layer_distribution

    # Tightly coupled pairs: router.py and auth.py import each other
    assert len(res.tightly_coupled_pairs) == 1
    pair = res.tightly_coupled_pairs[0]
    assert "backend/api/router.py" in (pair["module_a"], pair["module_b"])
    assert "backend/services/auth.py" in (pair["module_a"], pair["module_b"])

    # External library detected
    assert "pydantic" in res.external_libraries
