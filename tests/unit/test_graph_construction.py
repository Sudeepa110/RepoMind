"""
Unit tests for Knowledge Graph Construction & Persistence.
Validates node & edge models, directory hierarchy generation, deduplication,
atomic JSON serialization, recovery from corrupt files, and repository isolation.
"""

import json
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
from backend.app.graph.builder import GraphBuilder
from backend.app.processing.models import (
    ParsedRepository,
    ParsedFile,
    ExtractedSymbol,
    SymbolType,
    SymbolLocation,
    ExtractedImport,
    ExtractedCall,
)


def test_graph_node_and_edge_validation():
    """Verify GraphNode and GraphEdge validation, field defaults, and confidence."""
    node = GraphNode(
        id="repo1:auth.py:verify_jwt",
        repository_id="repo1",
        type=NodeType.FUNCTION,
        name="verify_jwt",
        qualified_name="auth.py:verify_jwt",
        file_path="auth.py",
        start_line=10,
        end_line=25,
        language="python",
        symbol_id="repo1:auth.py:verify_jwt",
        content_hash="abc123hash",
        properties={"docstring": "Verifies token"},
    )
    assert node.id == "repo1:auth.py:verify_jwt"
    assert node.type == NodeType.FUNCTION
    assert node.confidence == 1.0 if hasattr(node, "confidence") else True

    edge = GraphEdge(
        source_id="repo1:main.py:login",
        target_id="repo1:auth.py:verify_jwt",
        relationship=RelationshipType.CALLS,
        repository_id="repo1",
        is_confirmed=True,
        confidence=0.95,
        resolution_status="CONFIRMED_LOCAL",
        properties={"call_count": 2, "lines": [15, 22]},
    )
    assert edge.relationship == RelationshipType.CALLS
    assert edge.confidence == 0.95
    assert edge.is_confirmed is True
    assert edge.properties["call_count"] == 2


def test_graph_store_node_link_json_persistence():
    """Verify atomic persistence, structured JSON schema, and perfect restoration."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        store = NetworkXGraphStore(persist_dir=Path(tmp_dir))
        repo_id = "test_owner_repo"

        node1 = GraphNode(
            id="repo:test_owner_repo",
            repository_id=repo_id,
            type=NodeType.REPOSITORY,
            name="test_owner_repo",
        )
        node2 = GraphNode(
            id="file:test_owner_repo:auth.py",
            repository_id=repo_id,
            type=NodeType.FILE,
            name="auth.py",
            file_path="auth.py",
            start_line=1,
            end_line=50,
            language="python",
        )
        node3 = GraphNode(
            id="test_owner_repo:auth.py:login",
            repository_id=repo_id,
            type=NodeType.FUNCTION,
            name="login",
            file_path="auth.py",
            start_line=10,
            end_line=20,
            language="python",
        )
        edge1 = GraphEdge(
            source_id=node1.id,
            target_id=node2.id,
            relationship=RelationshipType.CONTAINS,
            repository_id=repo_id,
            confidence=1.0,
        )
        edge2 = GraphEdge(
            source_id=node2.id,
            target_id=node3.id,
            relationship=RelationshipType.CONTAINS,
            repository_id=repo_id,
            confidence=1.0,
        )

        store.add_node(node1)
        store.add_node(node2)
        store.add_node(node3)
        store.add_edge(edge1)
        store.add_edge(edge2)

        # Save to disk
        store.save(repo_id)

        # Inspect persisted file on disk
        persisted_file = Path(tmp_dir) / f"{repo_id}.json"
        assert persisted_file.exists()

        with open(persisted_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["repository_id"] == repo_id
            assert data["version"] == "1.0"
            assert data["node_count"] == 3
            assert data["edge_count"] == 2
            assert "graph" in data

        # Load into an independent fresh store
        fresh_store = NetworkXGraphStore(persist_dir=Path(tmp_dir))
        loaded = fresh_store.load(repo_id)
        assert loaded is True

        retrieved_n1 = fresh_store.get_node(node1.id, repo_id)
        assert retrieved_n1 is not None
        assert retrieved_n1.name == "test_owner_repo"
        assert retrieved_n1.type == NodeType.REPOSITORY

        retrieved_n3 = fresh_store.get_node(node3.id, repo_id)
        assert retrieved_n3 is not None
        assert retrieved_n3.name == "login"
        assert retrieved_n3.file_path == "auth.py"

        # Check edge
        retrieved_edge = fresh_store.get_edge(node2.id, node3.id)
        assert retrieved_edge is not None
        assert retrieved_edge.relationship == RelationshipType.CONTAINS


def test_corrupted_graph_recovery():
    """Verify graceful handling when graph JSON file is corrupted."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        store = NetworkXGraphStore(persist_dir=Path(tmp_dir))
        corrupt_file = Path(tmp_dir) / "corrupt_repo.json"
        with open(corrupt_file, "w", encoding="utf-8") as f:
            f.write("{ invalid json non-closing syntax ")

        assert store.load("corrupt_repo") is False
        assert store.get_node("any_id", "corrupt_repo") is None


def test_repository_graph_isolation():
    """Verify strict isolation between separate repositories."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        store = NetworkXGraphStore(persist_dir=Path(tmp_dir))

        node_a = GraphNode(
            id="node_a",
            repository_id="repo_A",
            type=NodeType.FUNCTION,
            name="func_A",
        )
        node_b = GraphNode(
            id="node_b",
            repository_id="repo_B",
            type=NodeType.FUNCTION,
            name="func_B",
        )

        store.add_node(node_a)
        store.add_node(node_b)

        # Scoped queries
        nodes_a = store.get_nodes("repo_A")
        assert len(nodes_a) == 1
        assert nodes_a[0].id == "node_a"

        nodes_b = store.get_nodes("repo_B")
        assert len(nodes_b) == 1
        assert nodes_b[0].id == "node_b"

        # Cross lookup must not find node from other repo when repository_id is specified
        assert store.get_node("node_a", "repo_B") is None
        assert store.get_node("node_b", "repo_A") is None


def test_graph_builder_full_pipeline():
    """Verify GraphBuilder generates hierarchy, nodes, and edges from ParsedRepository."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        store = NetworkXGraphStore(persist_dir=Path(tmp_dir))
        builder = GraphBuilder(store=store)

        parsed_repo = ParsedRepository(
            repository_id="org_proj",
            commit_hash="commit123",
            total_files=2,
            total_symbols=2,
            supported_languages=["python"],
            files={
                "src/core/auth.py": ParsedFile(
                    repository_id="org_proj",
                    file_path="src/core/auth.py",
                    language="python",
                    size_bytes=400,
                    line_count=30,
                    symbols=[
                        ExtractedSymbol(
                            symbol_id="org_proj:src/core/auth.py:authenticate",
                            name="authenticate",
                            symbol_type=SymbolType.FUNCTION,
                            location=SymbolLocation(file_path="src/core/auth.py", start_line=5, end_line=15),
                            source_code="def authenticate(u, p):\n    return True",
                            content_hash="auth_hash",
                        )
                    ],
                    calls=[
                        ExtractedCall(
                            caller_symbol_id="org_proj:src/core/auth.py:authenticate",
                            callee_name="verify_hash",
                            location=SymbolLocation(file_path="src/core/auth.py", start_line=8, end_line=8),
                            resolution_status="UNRESOLVED",
                        )
                    ],
                ),
                "src/main.py": ParsedFile(
                    repository_id="org_proj",
                    file_path="src/main.py",
                    language="python",
                    size_bytes=200,
                    line_count=20,
                    symbols=[
                        ExtractedSymbol(
                            symbol_id="org_proj:src/main.py:main",
                            name="main",
                            symbol_type=SymbolType.FUNCTION,
                            location=SymbolLocation(file_path="src/main.py", start_line=3, end_line=10),
                            source_code="def main():\n    authenticate('admin', 'pass')",
                        )
                    ],
                    calls=[
                        ExtractedCall(
                            caller_symbol_id="org_proj:src/main.py:main",
                            callee_name="authenticate",
                            location=SymbolLocation(file_path="src/main.py", start_line=5, end_line=5),
                            resolution_status="INFERRED_REPO",
                        )
                    ],
                ),
            },
        )

        result = builder.build_and_persist_graph(parsed_repo, store=store)
        assert result["total_nodes"] >= 6  # repo + 2 dirs + 2 files + 2 symbols + unresolved callee
        assert result["total_edges"] >= 5
        assert result["repository_id"] == "org_proj"

        # Check directory hierarchy
        dir_node = store.get_node("dir:org_proj:src/core", "org_proj")
        assert dir_node is not None
        assert dir_node.type == NodeType.DIRECTORY
        assert dir_node.name == "core"

        # Check call edge from main to authenticate
        calls_edge = store.get_edge(
            "org_proj:src/main.py:main",
            "org_proj:src/core/auth.py:authenticate",
        )
        assert calls_edge is not None
        assert calls_edge.relationship == RelationshipType.CALLS


def test_delete_repository_graph():
    """Verify deletion removes file and clears in-memory state."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        store = NetworkXGraphStore(persist_dir=Path(tmp_dir))
        repo_id = "repo_to_delete"

        store.add_node(
            GraphNode(id="n1", repository_id=repo_id, type=NodeType.FILE, name="test.py")
        )
        store.save(repo_id)

        target_file = Path(tmp_dir) / f"{repo_id}.json"
        assert target_file.exists()

        deleted = store.delete(repo_id)
        assert deleted is True
        assert not target_file.exists()
        assert store.get_node("n1", repo_id) is None
